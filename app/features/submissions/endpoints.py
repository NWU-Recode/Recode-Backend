from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, model_validator
from typing import Dict

from app.common.deps import CurrentUser, get_current_user, require_role
from app.features.submissions.schemas import QuestionEvaluationRequest, QuestionEvaluationResponse
from app.features.submissions.service import submissions_service
from app.features.submissions.repository import submissions_repository
from app.features.challenges.repository import challenge_repository
from app.DB.supabase import get_supabase


router = APIRouter(prefix="/submissions", tags=["submissions"], dependencies=[Depends(require_role("student"))])


class BatchSubmissionsPayload(BaseModel):
    submissions: Dict[str, str]

    @model_validator(mode="after")
    def validate_payload(cls, values: dict):
        subs = values.get("submissions") or {}
        if not isinstance(subs, dict):
            raise ValueError("submissions must be an object mapping question_id -> source_code")
        if len(subs) == 0:
            raise ValueError("submissions must contain at least one question entry")
        if len(subs) > 5:
            raise ValueError("submissions may contain at most 5 questions in a snapshot")
        for k, v in subs.items():
            if not isinstance(k, str) or not k:
                raise ValueError("question ids must be non-empty strings")
            if not isinstance(v, str):
                raise ValueError("source code must be a string")
        return values


@router.post(
    "/questions/{question_id}/quick-test",
    response_model=QuestionEvaluationResponse,
    summary="Run only the public test for a question (question_id only)",
)
async def quick_test_question_by_qid(
    question_id: str,
    payload: QuestionEvaluationRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Resolve question -> challenge and run ONLY public tests. Delegates to submissions_service.evaluate_question.

    Expects FE to send question_id and source_code. Returns the QuestionEvaluationResponse from the service.
    """
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
            source_code=payload.source_code,
            language_id=lang,
            include_private=False,
            user_id=current_user.id,
            attempt_number=1,
            late_multiplier=1.0,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/challenges/{challenge_id}/submit-challenge",
    response_model=dict,
    summary="Submit a snapshot challenge (batch) - uses up to 5 snapshot questions",
)
async def submit_challenge(
    challenge_id: str,
    payload: BatchSubmissionsPayload = Body(...),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Full snapshot submit flow (FE provides mapping question_id -> source_code). This
    uses the open attempt lifecycle: create_or_get_open_attempt, grade via service, and finalize attempt.
    """
    # payload validation is handled by BatchSubmissionsPayload defined at module scope

    try:
        student_number = current_user.id
        attempt = await challenge_repository.create_or_get_open_attempt(challenge_id, student_number)
        attempt_id = attempt.get("id")
        snapshot = attempt.get("snapshot_questions") or []

        # Build language_overrides map and question_weights from snapshot
        language_overrides = {str(q.get("question_id")): q.get("language_id") for q in snapshot}
        question_weights = {str(q.get("question_id")): q.get("points", 1) for q in snapshot}
        attempt_counts = {str(q.get("question_id")): int(q.get("attempts_used", 0)) for q in snapshot}

        # Delegate grading (service persists results and triggers awarding RPCs)
        subs_map = payload.submissions

        # Delegate grading (service persists results but we will perform RPC awarding in a post-step)
        breakdown = await submissions_service.grade_challenge_submission(
            challenge_id=challenge_id,
            attempt_id=attempt_id,
            submissions=subs_map,
            language_overrides=language_overrides,
            question_weights=question_weights,
            user_id=current_user.id,
            tier=attempt.get("tier") or "base",
            attempt_counts=attempt_counts,
            max_attempts=3,
            late_multiplier=1.0,
            perform_award=False,
        )

        # Post-process awarding: batch the passed public tests and call RPCs in a tight loop
        awards: Dict[str, list] = {}
        try:
            client = await get_supabase()
            for qres in getattr(breakdown, "question_results", []) or []:
                q_awards: list = []
                try:
                    for test_run in getattr(qres, "tests", []) or []:
                        if getattr(test_run, "passed", False) and getattr(test_run, "visibility", "public") == "public":
                            resp = await client.rpc(
                                "record_test_result_and_award",
                                {
                                    "p_profile_id": int(current_user.id),
                                    "p_question_id": str(getattr(qres, "question_id", "")),
                                    "p_test_id": str(getattr(test_run, "test_id", "")),
                                    "p_is_public": True,
                                    "p_passed": True,
                                    "p_public_badge_id": getattr(qres, "badge_tier_awarded", None),
                                },
                            ).execute()
                            # Supabase client execute returns a result with `.data` field (list of rows)
                            try:
                                data = getattr(resp, "data", None)
                            except Exception:
                                data = None
                            q_awards.append({"test_id": getattr(test_run, "test_id", None), "rpc_result": data})
                except Exception:
                    import logging

                    logging.getLogger("submissions").exception("Award RPC failed for question %s", getattr(qres, "question_id", None))
                    # keep whatever we have
                if q_awards:
                    awards[str(getattr(qres, "question_id", ""))] = q_awards
        except Exception:
            # If supabase client acquisition fails, swallow and continue
            awards = {}

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

        result_payload = {"result": breakdown.model_dump(), "awards": awards}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return result_payload

        


__all__ = ["router"]
