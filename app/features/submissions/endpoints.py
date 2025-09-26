from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.common.deps import CurrentUser, get_current_user_from_cookie
from app.features.submissions.schemas import (
    QuestionBundleSchema,
    QuestionEvaluationRequest,
    QuestionEvaluationResponse,
)
from app.features.submissions.service import submissions_service
from app.features.challenges.repository import challenge_repository
from app.features.submissions.code_results_repository import code_results_repository
from app.common.deps import get_current_user_from_cookie, CurrentUser
from fastapi import Body
from fastapi import BackgroundTasks
import asyncio, logging, time
from app.features.judge0.service import judge0_service
from app.features.judge0.schemas import CodeSubmissionCreate

router = APIRouter(prefix="/submissions", tags=["submissions"])


@router.get(
    "/challenges/{challenge_id}/questions/{question_id}",
    response_model=QuestionBundleSchema,
    summary="Fetch a question with its test cases",
)
async def get_question_bundle(
    challenge_id: str,
    question_id: str,
    current_user: CurrentUser = Depends(get_current_user_from_cookie),
):
    try:
        return await submissions_service.get_question_bundle(challenge_id, question_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/challenges/{challenge_id}/questions/{question_id}/evaluate",
    response_model=QuestionEvaluationResponse,
    summary="Execute Judge0 tests for a question",
)
async def evaluate_question(
    challenge_id: str,
    question_id: str,
    payload: QuestionEvaluationRequest,
    current_user: CurrentUser = Depends(get_current_user_from_cookie),
):
    try:
        return await submissions_service.evaluate_question(
            challenge_id,
            question_id,
            payload.source_code,
            payload.language_id,
            include_private=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/challenges/{challenge_id}/submit-question",
    response_model=QuestionEvaluationResponse,
    summary="Submit a single question attempt (uses attempts and persists results)",
)
async def submit_question(
    challenge_id: str,
    payload: QuestionEvaluationRequest = Body(...),
    current_user: CurrentUser = Depends(get_current_user_from_cookie),
):
    """Submit a single question. Honors attempt limits and persists results to code_submissions/code_results."""
    try:
        # The submissions_service.evaluate_question already persists results via code_results_repository.log_test_batch
        # We need to provide user_id and attempt metadata; attempt tracking occurs in challenge_repository
        # Resolve open attempt for the user
        student_number = current_user.id
        attempt = await challenge_repository.create_or_get_open_attempt(challenge_id, student_number)
        attempt_id = attempt.get("id")
        # Determine attempt count for this question
        snapshot = attempt.get("snapshot_questions") or []
        attempts_map = {str(i.get("question_id")): int(i.get("attempts_used", 0)) for i in snapshot}
        question_id = None
        # This endpoint expects payload to include a question_id via query param mapping to a single question
        # For compatibility, try to infer question id from the challenge snapshot if only one question
        if snapshot and len(snapshot) == 1:
            question_id = str(snapshot[0].get("question_id"))
        else:
            raise HTTPException(status_code=400, detail="question_id_missing_or_ambiguous")

        attempt_count = attempts_map.get(question_id, 0)
        if attempt_count >= 3:
            raise HTTPException(status_code=403, detail="attempt_limit_reached")

        resp = await submissions_service.evaluate_question(
            challenge_id,
            question_id,
            payload.source_code,
            payload.language_id,
            include_private=True,
            user_id=current_user.id,
            attempt_number=attempt_count + 1,
            late_multiplier=1.0,
        )

        # Record attempt increment
        await challenge_repository.record_question_attempts(attempt_id, {question_id: 1}, max_attempts=3)

        return resp
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/challenges/{challenge_id}/submit-challenge",
    response_model=dict,
    summary="Submit a snapshot challenge (batch) - uses up to 5 snapshot questions",
)
async def submit_challenge(
    challenge_id: str,
    submissions: dict = Body(...),
    current_user: CurrentUser = Depends(get_current_user_from_cookie),
):
    """Submit multiple questions according to the user's current open attempt snapshot.

    The `submissions` body should be a mapping of question_id -> source_code.
    """
    try:
        student_number = current_user.id
        attempt = await challenge_repository.create_or_get_open_attempt(challenge_id, student_number)
        attempt_id = attempt.get("id")
        snapshot = attempt.get("snapshot_questions") or []
        # Build language_overrides map and question_weights
        language_overrides = {str(q.get("question_id")): q.get("language_id") for q in snapshot}
        question_weights = {str(q.get("question_id")): q.get("points", 1) for q in snapshot}
        attempt_counts = {str(q.get("question_id")): int(q.get("attempts_used", 0)) for q in snapshot}

        # Run grading over the batch
        breakdown = await submissions_service.grade_challenge_submission(
            challenge_id=challenge_id,
            attempt_id=attempt_id,
            submissions=submissions,
            language_overrides=language_overrides,
            question_weights=question_weights,
            user_id=current_user.id,
            tier=attempt.get("tier") or "base",
            attempt_counts=attempt_counts,
            max_attempts=3,
            late_multiplier=1.0,
        )

        # Update challenge attempt finalization
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

        return {"result": breakdown.model_dump()}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


async def _background_poll_and_persist(token: str, user_id: int, language_id: int, source_code: str):
    """Background helper: poll Judge0 for token and persist results to code_submissions/code_results."""
    logger = logging.getLogger(__name__)
    start = time.time()
    timeout_seconds = 120
    poll_interval = 1.0
    while time.time() - start < timeout_seconds:
        try:
            res = await judge0_service.get_submission_result(token)
        except Exception as e:
            logger.debug("Background poll failed to fetch Judge0 result: %s", str(e))
            await asyncio.sleep(poll_interval)
            continue
        status_id = res.status.get("id") if res.status else None
        if status_id not in [1, 2]:
            # Convert to record and persist
            out = {
                "token": token,
                "status_id": status_id,
                "status_description": (res.status or {}).get("description", "unknown"),
                "stdout": res.stdout,
                "stderr": res.stderr,
                "time": res.time,
                "memory": res.memory,
                "language": res.language,
            }
            try:
                sub_id = await code_results_repository.create_submission(
                    user_id=user_id,
                    language_id=language_id or -1,
                    source_code=source_code,
                    token=token,
                )
                if sub_id:
                    await code_results_repository.insert_results(sub_id, [out])
            except Exception:
                logger.exception("Failed to persist background Judge0 result")
            return
        await asyncio.sleep(poll_interval)


@router.post(
    "/challenges/{challenge_id}/submit-question-async",
    response_model=dict,
    summary="Submit a single question attempt asynchronously (returns token and submission_id)",
)
async def submit_question_async(
    challenge_id: str,
    background_tasks: BackgroundTasks,
    payload: QuestionEvaluationRequest = Body(...),
    current_user: CurrentUser = Depends(get_current_user_from_cookie),
):
    try:
        # Infer question id same as submit_question (compatibility)
        student_number = current_user.id
        attempt = await challenge_repository.create_or_get_open_attempt(challenge_id, student_number)
        snapshot = attempt.get("snapshot_questions") or []
        if not snapshot or len(snapshot) != 1:
            raise HTTPException(status_code=400, detail="question_id_missing_or_ambiguous")
        question_id = str(snapshot[0].get("question_id"))

        # Submit to Judge0 to get token
        cs = CodeSubmissionCreate(source_code=payload.source_code, language_id=payload.language_id, stdin=None, expected_output=None)
        judge_resp = await judge0_service.submit_code(cs)
        token = judge_resp.token

        # Create code_submissions row immediately
        try:
            submission_id = await code_results_repository.create_submission(
                user_id=current_user.id,
                language_id=payload.language_id or -1,
                source_code=payload.source_code,
                token=token,
            )
        except Exception:
            logging.getLogger(__name__).exception("Failed to create submission row (async submit)")
            submission_id = None

        # Schedule background poll to persist results
        background_tasks.add_task(_background_poll_and_persist, token, current_user.id, payload.language_id, payload.source_code)

        return {"token": token, "submission_id": submission_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/challenges/{challenge_id}/submit-challenge-async",
    response_model=dict,
    summary="Submit a snapshot challenge asynchronously (returns tokens and submission_ids)",
)
async def submit_challenge_async(
    challenge_id: str,
    background_tasks: BackgroundTasks,
    submissions: dict = Body(...),
    current_user: CurrentUser = Depends(get_current_user_from_cookie),
):
    try:
        student_number = current_user.id
        attempt = await challenge_repository.create_or_get_open_attempt(challenge_id, student_number)
        snapshot = attempt.get("snapshot_questions") or []
        # Submit each provided source to Judge0 and create code_submissions rows
        tokens_and_ids = {}
        for qid, src in submissions.items():
            lang = next((q.get("language_id") for q in snapshot if str(q.get("question_id")) == str(qid)), None) or 71
            cs = CodeSubmissionCreate(source_code=src, language_id=lang, stdin=None, expected_output=None)
            judge_resp = await judge0_service.submit_code(cs)
            token = judge_resp.token
            try:
                submission_id = await code_results_repository.create_submission(
                    user_id=current_user.id,
                    language_id=lang,
                    source_code=src,
                    token=token,
                )
            except Exception:
                logging.getLogger(__name__).exception("Failed to create submission row (async challenge submit)")
                submission_id = None
            background_tasks.add_task(_background_poll_and_persist, token, current_user.id, lang, src)
            tokens_and_ids[qid] = {"token": token, "submission_id": submission_id}

        return {"result": tokens_and_ids}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/challenges/{challenge_id}/questions/{question_id}/quick-test",
    response_model=QuestionEvaluationResponse,
    summary="Run only the public test for quick feedback",
)
async def quick_test_question(
    challenge_id: str,
    question_id: str,
    payload: QuestionEvaluationRequest,
    current_user: CurrentUser = Depends(get_current_user_from_cookie),
):
    try:
        return await submissions_service.evaluate_question(
            challenge_id,
            question_id,
            payload.source_code,
            payload.language_id,
            include_private=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


__all__ = ["router"]
