from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.common.deps import CurrentUser, get_current_user_from_cookie
from app.features.submissions.schemas import (
    QuestionBundleSchema,
    QuestionEvaluationRequest,
    QuestionEvaluationResponse,
)
from app.features.submissions.service import submissions_service

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
