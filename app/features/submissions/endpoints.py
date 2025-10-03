from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, model_validator
from typing import Dict

from app.common.deps import CurrentUser, get_current_user, require_role
from app.features.submissions.schemas import (
    QuestionEvaluationRequest,
    QuestionEvaluationResponse,
    QuestionSubmissionRequest,
    BatchSubmissionEntry,
)
from app.features.submissions.service import submissions_service
from app.features.submissions.repository import submissions_repository
from app.features.challenges.repository import challenge_repository
from app.features.achievements.service import achievements_service
from app.features.achievements.schemas import CheckAchievementsRequest


router = APIRouter(prefix="/submissions", tags=["submissions"], dependencies=[Depends(require_role("student"))])


class BatchSubmissionsPayload(BaseModel):
    submissions: Dict[str, BatchSubmissionEntry]

    @model_validator(mode="after")
    def validate_payload(cls, values: dict):
        subs = values.get("submissions") or {}
        if not isinstance(subs, dict):
            raise ValueError("submissions must be an object mapping question_id -> {output}")
        if len(subs) == 0:
            raise ValueError("submissions must contain at least one question entry")
        if len(subs) > 5:
            raise ValueError("submissions may contain at most 5 questions in a snapshot")
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
        values["submissions"] = cleaned
        return values


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
        lang = int(payload.language_id or 71)
        return await submissions_service.evaluate_question(
            challenge_id=challenge_id,
            question_id=question_id,
            submitted_output=payload.output,
            language_id=lang,
            include_private=False,
            user_id=student_number,
            attempt_number=1,
            late_multiplier=1.0,
            perform_award=False,
            record_result=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/challenges/{challenge_id}/questions/{question_id}/submit",
    response_model=QuestionEvaluationResponse,
    summary="Submit output for a single challenge question (tracked attempt)",
    description=(
        "Grades the learner's output against the expected answer for the question and records "
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
        return await submissions_service.submit_question(
            challenge_id=challenge_id,
            question_id=question_id,
            submitted_output=payload.output,
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
    summary="Submit outputs for an active challenge snapshot",
    description=(
        "Grades all snapshot questions (up to five for base challenges) using expected output matching, "
        "persists the attempt, and triggers ELO/GPA/badge updates for the student."
    ),
)
async def submit_challenge(
    challenge_id: str,
    payload: BatchSubmissionsPayload = Body(...),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Full snapshot submit flow using expected-output grading for each question."""
    # payload validation is handled by BatchSubmissionsPayload defined at module scope

    try:
        student_number = int(current_user.id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_student_number")
    try:
        attempt = await challenge_repository.create_or_get_open_attempt(challenge_id, student_number)
        attempt_id = attempt.get("id")
        snapshot = attempt.get("snapshot_questions") or []

        # Build language_overrides map and question_weights from snapshot
        language_overrides = {str(q.get("question_id")): q.get("language_id") for q in snapshot}
        question_weights = {str(q.get("question_id")): q.get("points", 1) for q in snapshot}
        attempt_counts = {str(q.get("question_id")): int(q.get("attempts_used", 0)) for q in snapshot}
        expected_outputs = {str(q.get("question_id")): q.get("expected_output") for q in snapshot}

        subs_map = payload.submissions

        breakdown = await submissions_service.submit_challenge(
            challenge_id=challenge_id,
            attempt_id=attempt_id,
            submissions=subs_map,
            language_overrides=language_overrides,
            question_weights=question_weights,
            expected_outputs=expected_outputs,
            user_id=student_number,
            tier=attempt.get("tier") or "base",
            attempt_counts=attempt_counts,
            max_attempts=3,
            late_multiplier=1.0,
            perform_award=False,
        )

        # Post-process awarding: batch the passed public tests and call RPCs in a tight loop
        awards: Dict[str, list] = {}

        # Finalize attempt using service results
        await challenge_repository.finalize_attempt(
            attempt_id=attempt_id,
            score=int(breakdown.gpa_score),
            correct_count=len(breakdown.passed_questions),
            duration_seconds=None,
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
        }
        performance_payload = {k: v for k, v in performance_payload.items() if v is not None}

        achievement_summary = None
        try:
            achievement_summary = await achievements_service.check_achievements(
                str(student_number),
                CheckAchievementsRequest(
                    submission_id=str(attempt_id),
                    elo_delta_override=int(breakdown.elo_delta),
                    badge_tiers=breakdown.badge_tiers_awarded,
                    performance=performance_payload if performance_payload else None,
                ),
            )
        except Exception:
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

