# app/features/submissions/endpoints.py
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, model_validator

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

# New imports for persistence
from app.DB.supabase import get_supabase

logger = logging.getLogger("submissions")

router = APIRouter(
    prefix="/submissions", tags=["submissions"], dependencies=[Depends(require_role("student"))]
)
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
    question_id: str, payload: QuestionEvaluationRequest, current_user: CurrentUser = Depends(get_current_user)
):
    """Resolve question -> challenge and run only the expected-output comparison for preview purposes."""
    try:
        student_number = int(current_user.id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_student_number")
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
            submitted_output=payload.output,
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
    challenge_id: str, question_id: str, current_user: CurrentUser = Depends(require_role("student", "lecturer"))
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
            "challenge_not_found": 404,
            "question_not_found": 404,
            "question_not_in_snapshot": 404,
            "attempt_limit_reached": 400,
            "challenge_already_submitted": 409,
            "challenge_attempt_expired": 409,
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

            logger.info(
                f"✅ Achievement summary created: ELO={achievement_summary.updated_elo if achievement_summary else 'None'}"
            )

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
                    questions_attempted = len(breakdown.question_results)
                    questions_passed = len(breakdown.passed_questions)
                    challenges_completed = 1 if questions_passed >= (questions_attempted * 0.5) else 0
                    total_badges = len(achievement_summary.unlocked_badges) if achievement_summary.unlocked_badges else 0

                    logger.info(
                        f"📊 Updating user_scores: attempted={questions_attempted}, passed={questions_passed}, badges={total_badges}"
                    )

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

            # ----------------------------
            # NEW: Persist rewards to DB
            # ----------------------------
            try:
                client = await get_supabase()

                # Helper to extract properties from achievement_summary safely
                def _extract(summary_obj: Any, key: str) -> Any:
                    try:
                        return getattr(summary_obj, key)
                    except Exception:
                        pass
                    try:
                        return summary_obj.get(key)
                    except Exception:
                        pass
                    try:
                        return summary_obj.model_dump().get(key)
                    except Exception:
                        return None

                # Collect common values
                updated_elo = _extract(achievement_summary, "updated_elo")
                previous_elo = _extract(achievement_summary, "previous_elo") or _extract(
                    achievement_summary, "previousElo"
                ) or None
                unlocked_badges = _extract(achievement_summary, "unlocked_badges") or _extract(
                    achievement_summary, "unlockedBadges"
                ) or []
                new_title_id = (
                    _extract(achievement_summary, "new_title_id")
                    or _extract(achievement_summary, "newTitleId")
                    or _extract(achievement_summary, "title_id")
                    or None
                )

                # If updated_elo is missing, compute from DB current value + breakdown.elo_delta
                if updated_elo is None and breakdown and isinstance(breakdown.elo_delta, int):
                    try:
                        resp = await client.table("user_elo").select("*").eq("student_id", student_number).limit(1).execute()
                        rows = getattr(resp, "data", None) or []
                        existing = rows[0] if rows else None
                        current_before = existing.get("current_elo") if existing else None
                        if current_before is not None:
                            previous_elo = int(current_before)
                            updated_elo = int(current_before) + int(breakdown.elo_delta)
                        else:
                            previous_elo = 0
                            updated_elo = int(breakdown.elo_delta)
                    except Exception:
                        previous_elo = None
                        updated_elo = None

                # Fetch profile to get supabase_id uuid for user_id field in elo_events
                profile_supabase_id = None
                try:
                    resp = await client.table("profiles").select("supabase_id").eq("id", student_number).limit(1).execute()
                    rows = getattr(resp, "data", None) or []
                    if rows:
                        profile_supabase_id = rows[0].get("supabase_id")
                except Exception:
                    profile_supabase_id = None

                # Persist user_elo (upsert)
                if updated_elo is not None:
                    try:
                        # fetch existing row to compute total_awarded_elo
                        try:
                            resp = await client.table("user_elo").select("*").eq("student_id", student_number).limit(1).execute()
                            rows = getattr(resp, "data", None) or []
                            existing = rows[0] if rows else None
                        except Exception:
                            existing = None

                        # Determine previous_elo fallback
                        if previous_elo is None:
                            try:
                                if existing and existing.get("current_elo") is not None:
                                    previous_elo = int(existing.get("current_elo"))
                                else:
                                    previous_elo = 0
                            except Exception:
                                previous_elo = 0

                        # Compute elo_delta_val (prefer breakdown.elo_delta)
                        try:
                            elo_delta_val = int(breakdown.elo_delta) if breakdown and hasattr(breakdown, "elo_delta") and breakdown.elo_delta is not None else (int(updated_elo) - int(previous_elo) if (previous_elo is not None and updated_elo is not None) else 0)
                        except Exception:
                            try:
                                elo_delta_val = int(updated_elo) - int(previous_elo)
                            except Exception:
                                elo_delta_val = 0

                        total_awarded = (existing.get("total_awarded_elo") if existing and existing.get("total_awarded_elo") is not None else 0)
                        try:
                            total_awarded = int(total_awarded) + int(elo_delta_val)
                        except Exception:
                            total_awarded = int(elo_delta_val)

                        upsert_payload = {
                            "student_id": student_number,
                            "current_elo": int(updated_elo),
                            "total_awarded_elo": total_awarded,
                            "last_awarded_at": datetime.now(timezone.utc).isoformat(),
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }
                        # Keep profile_id if present in existing row (defensive)
                        if existing and existing.get("profile_id") is not None:
                            upsert_payload["profile_id"] = existing.get("profile_id")

                        await client.table("user_elo").upsert(upsert_payload).execute()
                        logger.info(f"   ✅ user_elo upserted for student={student_number} current_elo={updated_elo}")
                    except Exception as ue:
                        logger.warning(f"   ❌ Failed to upsert user_elo for student {student_number}: {ue}")

                    # Insert a single elo_events audit record
                    try:
                        event_payload = {
                            "user_id": profile_supabase_id,
                            "student_id": student_number,
                            "event_type": "challenge_submission",
                            "elo_change": int(elo_delta_val) if 'elo_delta_val' in locals() else (int(updated_elo) - int(previous_elo) if (previous_elo is not None and updated_elo is not None) else 0),
                            "elo_before": int(previous_elo) if previous_elo is not None else None,
                            "elo_after": int(updated_elo) if updated_elo is not None else None,
                            "challenge_id": challenge_id,
                            "attempt_id": str(attempt_id),
                            "submission_id": str(attempt_id),
                            "question_id": None,
                            "metadata": {
                                "gpa_score": getattr(breakdown, "gpa_score", None) if breakdown else None,
                                "tests_total": getattr(breakdown, "tests_total", None) if breakdown else None,
                                "tests_passed": getattr(breakdown, "tests_passed_total", None) if breakdown else None,
                            },
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        }
                        # Clean None values (Supabase client tolerates missing keys but this keeps payload tidy)
                        event_payload = {k: v for k, v in event_payload.items() if v is not None}
                        await client.table("elo_events").insert(event_payload).execute()
                        logger.info(f"   ✅ elo_events inserted for student={student_number}")
                    except Exception as ee:
                        logger.warning(f"   ❌ Failed to insert elo_events for student {student_number}: {ee}")

                # Persist badges (if any)
                try:
                    if unlocked_badges:
                        # unlocked_badges may be list of dicts or strings - normalize to list of ids
                        badge_ids: list = []
                        if isinstance(unlocked_badges, (list, tuple)):
                            for item in unlocked_badges:
                                if isinstance(item, dict):
                                    bid = item.get("id") or item.get("badge_id") or item.get("badgeId")
                                    if bid:
                                        badge_ids.append(bid)
                                else:
                                    badge_ids.append(item)
                        elif isinstance(unlocked_badges, str):
                            badge_ids = [unlocked_badges]
                        else:
                            badge_ids = []

                        for bid in badge_ids:
                            try:
                                badge_payload = {
                                    "profile_id": student_number,
                                    "badge_id": str(bid),
                                    "date_earned": datetime.now(timezone.utc).isoformat(),
                                    "question_id": None,
                                }
                                await client.table("user_badge").insert(badge_payload).execute()
                                logger.info(f"   ✅ user_badge inserted for student={student_number} badge={bid}")
                            except Exception as ub_err:
                                logger.warning(f"   ❌ Failed to insert user_badge for student {student_number} badge {bid}: {ub_err}")
                except Exception as badges_err:
                    logger.warning(f"   ❌ Badges persistence failed: {badges_err}")

                # Persist title change if present
                if new_title_id:
                    try:
                        await client.table("profiles").update({"title_id": new_title_id}).eq("id", student_number).execute()
                        logger.info(f"   ✅ profiles.title_id updated for student={student_number} -> title={new_title_id}")
                    except Exception as title_err:
                        logger.warning(f"   ❌ Failed to update profiles.title_id for student {student_number}: {title_err}")

            except Exception as persist_err:
                logger.warning(f"⚠️ Reward persistence failed (non-fatal): {persist_err}")

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
