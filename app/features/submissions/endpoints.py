from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, model_validator
from typing import Dict, Optional

from app.common.deps import CurrentUser, get_current_user, require_role
from app.features.submissions.schemas import (
    QuestionEvaluationRequest,
    QuestionEvaluationResponse,
    QuestionSubmissionRequest,
    QuestionBundleSchema,
    BatchSubmissionEntry,
)
from app.features.submissions.service import submissions_service
from app.features.submissions.repository import submissions_repository
from app.features.challenges.repository import challenge_repository
from app.features.achievements.service import achievements_service
from app.features.achievements.schemas import CheckAchievementsRequest

logger = logging.getLogger("submissions")


router = APIRouter(prefix="/submissions", tags=["submissions"], dependencies=[Depends(require_role("student"))])
router_mixed = APIRouter(prefix="/submissions", tags=["submissions"])

class BatchSubmissionsPayload(BaseModel):
    submissions: Dict[str, BatchSubmissionEntry]
    duration_seconds: Optional[int] = None

    @model_validator(mode="after")
    def validate_payload(cls, model: "BatchSubmissionsPayload") -> "BatchSubmissionsPayload":
        subs = model.submissions or {}
        if not isinstance(subs, dict):
            raise ValueError("submissions must be an object mapping question_id -> {source_code}")
        if len(subs) == 0:
            raise ValueError("submissions must contain at least one question entry")
        if len(subs) > 5:
            raise ValueError("submissions may contain at most 5 questions in a snapshot")
        if model.duration_seconds is not None:
            try:
                duration_val = int(model.duration_seconds)
            except Exception as exc:  # pragma: no cover - defensive typing
                raise ValueError("duration_seconds must be an integer") from exc
            if duration_val < 0:
                raise ValueError("duration_seconds must be non-negative")
            model.duration_seconds = duration_val
        cleaned: Dict[str, BatchSubmissionEntry] = {}
        for k, v in subs.items():
            if not isinstance(k, str) or not k:
                raise ValueError("question ids must be non-empty strings")
            if isinstance(v, BatchSubmissionEntry):
                cleaned[k] = v
                continue
            try:
                cleaned[k] = BatchSubmissionEntry.validate_entry(v)  # type: ignore[arg-type]
            except ValueError as exc:
                raise ValueError(str(exc))
        model.submissions = cleaned
        return model


@router.post(
    "/questions/{question_id}/quick-test",
    response_model=QuestionEvaluationResponse,
    summary="Perform a quick expected-output check for a question",
    description=(
        "Compares the learner's provided output with the stored expected output for the question. "
        "This endpoint does not persist any attempt data or affect ELO/GPA; it is intended for "
        "front-end preview before submitting a full challenge snapshot."
    ),
)
async def quick_test_question_by_qid(
    question_id: str,
    payload: QuestionEvaluationRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Resolve question -> challenge and run only the expected-output comparison for preview purposes."""
    try:
        student_number = int(current_user.id)
    except Exception:
        raise HTTPException(status_code=400, detail='invalid_student_number')
    q = await submissions_repository.get_question(question_id)
    if not q:
        raise HTTPException(status_code=404, detail="question_not_found")
    challenge_id = str(q.get("challenge_id")) if q.get("challenge_id") else None
    if challenge_id is None:
        raise HTTPException(status_code=400, detail="question_missing_challenge")

    try:
        return await submissions_service.evaluate_question(
            challenge_id=challenge_id,
            question_id=question_id,
            submitted_output=payload.output,  # Use the output from payload, not hardcoded None
            source_code=payload.source_code,
            language_id=payload.language_id,
            include_private=False,
            user_id=student_number,
            attempt_number=1,
            late_multiplier=1.0,
            perform_award=False,
            record_result=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router_mixed.get(
    "/challenges/{challenge_id}/questions/{question_id}/bundle",
    response_model=QuestionBundleSchema,
    summary="(debug) Return the question bundle including tests",
)
async def get_question_bundle_debug(
    challenge_id: str,
    question_id: str,
    current_user: CurrentUser = Depends(require_role("student", "lecturer"))
):
    try:
        return await submissions_service.get_question_bundle(challenge_id, question_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/challenges/{challenge_id}/questions/{question_id}/submit",
    response_model=QuestionEvaluationResponse,
    summary="Submit source code for a single challenge question (tracked attempt)",
    description=(
        "Runs the learner's source code against the expected answer for the question and records "
        "progress within the active challenge attempt. Passing results count toward ELO/GPA "
        "updates once the full challenge snapshot is finalised."
    ),
)
async def submit_question(
    challenge_id: str,
    question_id: str,
    payload: QuestionSubmissionRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    try:
        student_number = int(current_user.id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_student_number")

    try:
        # Force full-test evaluation for single-question submit so GPA/ELO are computed
        # consistently (we no longer rely on visibility labels).
        return await submissions_service.submit_question(
            challenge_id=challenge_id,
            question_id=question_id,
            submitted_output=None,
            source_code=payload.source_code,
            user_id=student_number,
            language_id=payload.language_id,
            include_private=payload.include_private,
        )
    except ValueError as exc:
        message = str(exc)
        status_map = {
            'challenge_not_found': 404,
            'question_not_found': 404,
            'question_not_in_snapshot': 404,
            'attempt_limit_reached': 400,
            'challenge_already_submitted': 409,
            'challenge_attempt_expired': 409,
        }
        raise HTTPException(status_code=status_map.get(message, 400), detail=message)


@router.post(
    "/challenges/{challenge_id}/submit-challenge",
    response_model=dict,
    summary="Submit source code for an active challenge snapshot",
    description=(
        "Runs each snapshot submission through Judge0 (up to five base questions), persists the attempt, "
        "and triggers ELO/GPA/badge updates for the student."
    ),
)
async def submit_challenge(
    challenge_id: str,
    payload: BatchSubmissionsPayload = Body(...),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Full snapshot submit flow using expected-output grading for each question."""
    # payload validation is handled by BatchSubmissionsPayload defined at module scope
    
    logger.info(f"🚀 SUBMIT_CHALLENGE CALLED: challenge={challenge_id[:8]}, user={current_user.id}")

    try:
        student_number = int(current_user.id)
        logger.info(f"   ✅ Student number converted: {student_number}")
    except Exception as e:
        logger.error(f"   ❌ Failed to convert user_id to int: {e}")
        raise HTTPException(status_code=400, detail="invalid_student_number")
    try:
        attempt = await challenge_repository.create_or_get_open_attempt(challenge_id, student_number)
        attempt_id = attempt.get("id")
        snapshot = attempt.get("snapshot_questions") or []

        started_at_raw = attempt.get("started_at")
        started_at_dt: Optional[datetime] = None
        if started_at_raw:
            try:
                started_at_dt = datetime.fromisoformat(str(started_at_raw).replace("Z", "+00:00"))
            except Exception:
                started_at_dt = None

        # Build language_overrides map and question_weights from snapshot
        language_overrides = {str(q.get("question_id")): q.get("language_id") for q in snapshot}
        question_weights = {str(q.get("question_id")): q.get("points", 1) for q in snapshot}
        attempt_counts = {str(q.get("question_id")): int(q.get("attempts_used", 0)) for q in snapshot}
        subs_map = payload.submissions

        breakdown = await submissions_service.submit_challenge(
            challenge_id=challenge_id,
            attempt_id=attempt_id,
            submissions=subs_map,
            language_overrides=language_overrides,
            question_weights=question_weights,
            user_id=student_number,
            tier=attempt.get("tier") or "base",
            attempt_counts=attempt_counts,
            max_attempts=3,
            started_at=started_at_dt,
            duration_seconds=payload.duration_seconds,
            perform_award=False,
        )

        # Post-process awarding: batch the passed public tests and call RPCs in a tight loop
        awards: Dict[str, list] = {}

        # Finalize attempt using service results
        await challenge_repository.finalize_attempt(
            attempt_id=attempt_id,
            score=int(breakdown.gpa_score),
            correct_count=len(breakdown.passed_questions),
            duration_seconds=breakdown.time_used_seconds,
            tests_total=breakdown.tests_total,
            tests_passed=breakdown.tests_passed_total,
            elo_delta=breakdown.elo_delta,
            efficiency_bonus=breakdown.efficiency_bonus_total,
        )

        # Trigger achievements engine to update ELO/GPA/badges based on the finalised attempt
        performance_payload = {
            "tests_total": breakdown.tests_total,
            "tests_passed_total": breakdown.tests_passed_total,
            "average_execution_time_ms": breakdown.average_execution_time_ms,
            "average_memory_used_kb": breakdown.average_memory_used_kb,
            "base_elo_total": breakdown.base_elo_total,
            "efficiency_bonus_total": breakdown.efficiency_bonus_total,
            "challenge_id": challenge_id,
            "tier": attempt.get("tier") or "base",
            "time_used_seconds": breakdown.time_used_seconds,
            "time_limit_seconds": breakdown.time_limit_seconds,
        }
        performance_payload = {k: v for k, v in performance_payload.items() if v is not None}

        logger.info(f"🚀 REACHED ACHIEVEMENT BLOCK! student_number={student_number}, type={type(student_number)}")
        logger.info(f"📋 Performance payload: {performance_payload}")
        logger.info(f"📊 Breakdown ELO: {breakdown.elo_delta}, Badges: {breakdown.badge_tiers_awarded}")
        
        achievement_summary = None
        try:
            logger.info(f"🎯 STARTING ACHIEVEMENT PROCESSING for student {student_number}")
            logger.info(f"   ELO Delta: {breakdown.elo_delta}, Badge Tiers: {breakdown.badge_tiers_awarded}")
            
            achievement_summary = await achievements_service.check_achievements(
                str(student_number),
                CheckAchievementsRequest(
                    submission_id=str(attempt_id),
                    elo_delta_override=int(breakdown.elo_delta),
                    badge_tiers=breakdown.badge_tiers_awarded,
                    performance=performance_payload if performance_payload else None,
                ),
            )
            
            logger.info(f"✅ Achievement summary created: ELO={achievement_summary.updated_elo if achievement_summary else 'None'}")
            
            # Update user_question_progress for each question
            from app.features.achievements.repository import AchievementsRepository
            achievements_repo = AchievementsRepository()
            
            for question_result in breakdown.question_results:
                try:
                    logger.info(f"📝 Updating question_progress for Q:{question_result.question_id[:8]}")
                    await achievements_repo.update_question_progress(
                        user_id=str(student_number),
                        question_id=str(question_result.question_id),
                        challenge_id=str(breakdown.challenge_id),
                        attempt_id=str(attempt_id),
                        tests_passed=question_result.tests_passed or 0,
                        tests_total=question_result.tests_total or 0,
                        elo_earned=question_result.elo_awarded or 0,
                        gpa_contribution=question_result.gpa_awarded or 0,
                    )
                    logger.info(f"   ✅ Question progress updated")
                except Exception as qp_err:
                    logger.warning(f"   ❌ Failed to update question_progress: {qp_err}")
                    pass  # Silently ignore if table doesn't exist
            
            # Update user_scores table with overall stats
            if achievement_summary:
                try:
                    # Count total questions attempted and passed
                    questions_attempted = len(breakdown.question_results)
                    questions_passed = len(breakdown.passed_questions)
                    challenges_completed = 1 if questions_passed >= (questions_attempted * 0.5) else 0  # 50% pass threshold
                    total_badges = len(achievement_summary.unlocked_badges) if achievement_summary.unlocked_badges else 0
                    
                    logger.info(f"📊 Updating user_scores: attempted={questions_attempted}, passed={questions_passed}, badges={total_badges}")
                    
                    await achievements_repo.update_user_scores(
                        user_id=str(student_number),
                        elo=achievement_summary.updated_elo,
                        gpa=achievement_summary.gpa,
                        questions_attempted=questions_attempted,
                        questions_passed=questions_passed,
                        challenges_completed=challenges_completed,
                        badges=total_badges,
                    )
                    
                    logger.info(f"   ✅ user_scores updated successfully")
                except Exception as scores_err:
                    logger.warning(f"   ❌ Failed to update user_scores: {scores_err}")
            else:
                logger.warning(f"⚠️ No achievement_summary - skipping user_scores update")
                    
        except Exception as achievement_err:
            logger.error(f"❌ Achievement processing failed: {achievement_err}")
            achievement_summary = None

        result_payload = {
            "result": breakdown.model_dump(),
            "awards": awards,
            "achievement_summary": achievement_summary.model_dump() if achievement_summary else None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return result_payload

        


__all__ = ["router"]

