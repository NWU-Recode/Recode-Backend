from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends, Body, Query
from app.common.deps import get_current_user, CurrentUser, require_role
from .schemas import (
    ChallengeSubmitRequest,
    ChallengeSubmitResponse,
    GetChallengeAttemptResponse,
    ChallengeAttemptQuestionStatus,
    ChallengeGenerateRequest,
    ChallengeListResponse,
    ChallengeSummaryItem,
    ChallengeDetailResponse,
    ChallengeQuestionSummary,
    QuestionListResponse,
    QuestionDetailResponse,
    QuestionTestCaseListResponse,
    QuestionDetail,
    QuestionSummary,
    QuestionTestCase,
)
from .service import challenge_service
from app.features.challenges.repository import challenge_repository
# Lazily import heavy generator functions at runtime to avoid import-time failures while
# challenge_pack_generator.py is being fixed or may raise syntax/indentation errors.
generate_tier_preview = None
generate_and_save_tier = None
from app.DB.supabase import get_supabase
from app.features.challenges.semester_orchestrator import semester_orchestrator
from typing import Dict, Any, Optional, List, Set

router = APIRouter(prefix="/challenges", tags=["challenges"], dependencies=[Depends(get_current_user)])

questions_router = APIRouter(prefix="/questions", tags=["questions"], dependencies=[Depends(get_current_user)])


def _parse_include(value: Optional[str]) -> Set[str]:
    if not value:
        return set()
    return {part.strip().lower() for part in value.split(',') if part.strip()}


def _parse_statuses(value: Optional[str]) -> List[str]:
    if not value:
        return ["active"]
    items = [part.strip().lower() for part in value.split(',') if part.strip()]
    return items or ["active"]


def _build_testcase_payload(data: Dict[str, Any]) -> QuestionTestCase:
    return QuestionTestCase(
        id=data.get("id"),
        stdin=data.get("input") or data.get("stdin"),
        expected_output=data.get("expected_output") or data.get("expected"),
        visibility=data.get("visibility"),
        order=data.get("order_index") or data.get("order")
    )


def _build_question_detail(data: Dict[str, Any], include_testcases: bool = False) -> QuestionDetail:
    testcases = None
    if include_testcases:
        raw_cases = data.get("testcases") or []
        testcases = [_build_testcase_payload(item) for item in raw_cases]
    return QuestionDetail(
        id=data.get("id"),
        challenge_id=data.get("challenge_id"),
        question_number=data.get("question_number"),
        sub_number=data.get("sub_number"),
        position=data.get("position"),
        prompt=data.get("prompt") or data.get("question_text"),
        question_text=data.get("question_text"),
        starter_code=data.get("starter_code"),
        reference_solution=data.get("reference_solution"),
        language_id=data.get("language_id"),
        tier=data.get("tier"),
        difficulty=data.get("difficulty"),
        samples=data.get("samples"),
        hints=data.get("hints"),
        testcases=testcases,
    )


def _build_question_summary(data: Dict[str, Any]) -> ChallengeQuestionSummary:
    return ChallengeQuestionSummary(
        id=data.get("id"),
        question_number=data.get("question_number"),
        sub_number=data.get("sub_number"),
        position=data.get("position"),
        prompt=data.get("prompt") or data.get("question_text"),
    )


def _build_challenge_summary(
    challenge: Dict[str, Any],
    *,
    question_count: int,
    questions: Optional[List[Dict[str, Any]]] = None,
    include_questions: bool = False,
) -> ChallengeSummaryItem:
    question_payload = None
    if include_questions and questions is not None:
        question_payload = [_build_question_summary(q) for q in questions]
    return ChallengeSummaryItem(
        id=challenge.get("id"),
        title=challenge.get("title"),
        slug=challenge.get("slug"),
        module_code=challenge.get("module_code"),
        semester_id=challenge.get("semester_id"),
        week_number=challenge.get("week_number"),
        status=challenge.get("status"),
        tier=challenge.get("tier"),
        challenge_type=challenge.get("challenge_type"),
        question_count=question_count,
        questions=question_payload,
    )


def _build_challenge_detail(challenge: Dict[str, Any], questions: List[Dict[str, Any]], include_questions: bool) -> ChallengeDetailResponse:
    question_payload = [_build_question_summary(q) for q in questions] if include_questions else None
    return ChallengeDetailResponse(
        id=challenge.get("id"),
        title=challenge.get("title"),
        slug=challenge.get("slug"),
        module_code=challenge.get("module_code"),
        semester_id=challenge.get("semester_id"),
        week_number=challenge.get("week_number"),
        status=challenge.get("status"),
        tier=challenge.get("tier"),
        challenge_type=challenge.get("challenge_type"),
        question_count=len(questions),
        description=challenge.get("description"),
        release_date=challenge.get("release_date"),
        due_date=challenge.get("due_date"),
        trigger_event=challenge.get("trigger_event"),
        questions=question_payload,
    )

# ---------------------------------------------
# Lecturer challenge generation
# ---------------------------------------------



@router.get("/", response_model=ChallengeListResponse, summary="List challenges for a module and week", tags=["challenges"])
async def list_challenges(
    module_code: str,
    week: int,
    status: Optional[str] = "active",
    include: Optional[str] = Query(None, description="Comma-delimited includes (e.g. questions)"),
    limit: int = Query(20, ge=1, le=100),
    cursor: Optional[str] = Query(None, description="Cursor returned from a previous request"),
    current_user: CurrentUser = Depends(get_current_user),
):
    if week <= 0:
        raise HTTPException(status_code=400, detail="week must be > 0")
    includes = _parse_include(include)
    include_questions = "questions" in includes
    statuses = _parse_statuses(status)
    try:
        module = await challenge_repository.resolve_module_access(module_code, current_user)
    except PermissionError:
        raise HTTPException(status_code=403, detail="module_access_denied") from None
    except ValueError as exc:
        message = str(exc)
        if message == "module_not_found":
            raise HTTPException(status_code=404, detail=message) from None
        raise HTTPException(status_code=400, detail=message) from None
    try:
        records, next_cursor = await challenge_repository.list_challenges_by_module_and_week(
            module_code=module.get("code") or module_code,
            week_number=week,
            statuses=statuses,
            include_questions=include_questions,
            limit=limit,
            cursor=cursor,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    items: List[ChallengeSummaryItem] = []
    for entry in records:
        challenge = entry.get("challenge") or {}
        questions = entry.get("questions") or []
        question_count = entry.get("question_count", len(questions))
        items.append(
            _build_challenge_summary(
                challenge,
                question_count=question_count,
                questions=questions,
                include_questions=include_questions,
            )
        )
    return ChallengeListResponse(items=items, next_cursor=next_cursor)


@router.get("/{challenge_id}", response_model=ChallengeDetailResponse, summary="Get challenge detail", tags=["challenges"])
async def get_challenge_detail(
    challenge_id: UUID,
    include: Optional[str] = Query(None, description="Comma-delimited includes (e.g. questions)"),
    current_user: CurrentUser = Depends(get_current_user),
):
    includes = _parse_include(include)
    include_questions = "questions" in includes
    try:
        bundle = await challenge_repository.fetch_challenge_with_questions(
            str(challenge_id),
            include_questions=include_questions,
            include_testcases=False,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="challenge_not_found") from None
    challenge = bundle.get("challenge") or {}
    module_code = challenge.get("module_code")
    if not module_code:
        raise HTTPException(status_code=404, detail="module_not_found")
    try:
        await challenge_repository.resolve_module_access(module_code, current_user)
    except PermissionError:
        raise HTTPException(status_code=403, detail="module_access_denied") from None
    except ValueError as exc:
        message = str(exc)
        if message == "module_not_found":
            raise HTTPException(status_code=404, detail=message) from None
        raise HTTPException(status_code=400, detail=message) from None

    questions_data = bundle.get("questions") or []
    if not include_questions:
        questions_data = await challenge_repository.get_challenge_questions(str(challenge_id))
    detail = _build_challenge_detail(challenge, questions_data, include_questions)
    return detail


@router.get("/{challenge_id}/questions", response_model=QuestionListResponse, summary="List questions for a challenge", tags=["challenges"])
async def list_challenge_questions(
    challenge_id: UUID,
    include: Optional[str] = Query(None, description="Comma-delimited includes (e.g. testcases)"),
    current_user: CurrentUser = Depends(get_current_user),
):
    includes = _parse_include(include)
    include_testcases = "testcases" in includes
    challenge = await challenge_repository.get_challenge(str(challenge_id))
    if not challenge:
        raise HTTPException(status_code=404, detail="challenge_not_found")
    module_code = challenge.get("module_code")
    try:
        await challenge_repository.resolve_module_access(module_code, current_user)
    except PermissionError:
        raise HTTPException(status_code=403, detail="module_access_denied") from None
    except ValueError as exc:
        message = str(exc)
        if message == "module_not_found":
            raise HTTPException(status_code=404, detail=message) from None
        raise HTTPException(status_code=400, detail=message) from None

    try:
        questions = await challenge_repository.list_questions_for_challenge(
            str(challenge_id), include_testcases=include_testcases
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    items = [_build_question_detail(q, include_testcases=include_testcases) for q in questions]
    return QuestionListResponse(items=items)


@questions_router.get("/{question_id}", response_model=QuestionDetailResponse, summary="Get question detail")
async def get_question_detail(
    question_id: UUID,
    include: Optional[str] = Query(None, description="Comma-delimited includes (testcases,solution,hints)"),
    current_user: CurrentUser = Depends(get_current_user),
):
    includes = _parse_include(include)
    include_testcases = "testcases" in includes
    try:
        question = await challenge_repository.fetch_question_detail(
            str(question_id), include_testcases=include_testcases
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not question:
        raise HTTPException(status_code=404, detail="question_not_found")
    challenge_id = question.get("challenge_id")
    challenge = await challenge_repository.get_challenge(str(challenge_id)) if challenge_id else None
    module_code = (challenge or {}).get("module_code")
    try:
        await challenge_repository.resolve_module_access(module_code, current_user)
    except PermissionError:
        raise HTTPException(status_code=403, detail="module_access_denied") from None
    except ValueError as exc:
        message = str(exc)
        if message == "module_not_found":
            raise HTTPException(status_code=404, detail=message) from None
        raise HTTPException(status_code=400, detail=message) from None
    detail = _build_question_detail(question, include_testcases=include_testcases)
    return QuestionDetailResponse(**detail.model_dump())


@questions_router.get("/{question_id}/testcases", response_model=QuestionTestCaseListResponse, summary="List testcases for a question")
async def get_question_testcases(
    question_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
):
    question = await challenge_repository.fetch_question_detail(str(question_id), include_testcases=False)
    if not question:
        raise HTTPException(status_code=404, detail="question_not_found")
    challenge_id = question.get("challenge_id")
    challenge = await challenge_repository.get_challenge(str(challenge_id)) if challenge_id else None
    module_code = (challenge or {}).get("module_code")
    try:
        await challenge_repository.resolve_module_access(module_code, current_user)
    except PermissionError:
        raise HTTPException(status_code=403, detail="module_access_denied") from None
    except ValueError as exc:
        message = str(exc)
        if message == "module_not_found":
            raise HTTPException(status_code=404, detail=message) from None
        raise HTTPException(status_code=400, detail=message) from None
    try:
        cases = await challenge_repository.list_question_testcases(str(question_id))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    items = [_build_testcase_payload(case) for case in cases]
    return QuestionTestCaseListResponse(items=items)

ALLOWED_TIERS = {"base", "ruby", "emerald", "diamond"}



@router.get("/semester/overview")
async def get_semester_overview(current_user: CurrentUser = Depends(get_current_user)):
    try:
        return await semester_orchestrator.get_release_overview(str(current_user.id))
    except Exception as e:
        raise HTTPException(status_code=400, detail={"error_code":"E_UNKNOWN","message":str(e)})


# NOTE: Publishing and published retrieval are now handled via slide uploads and /active/{week_number} respectively.
# The old POST /publish/{week_number} and GET /published/{week_number} endpoints were intentionally removed.





@router.get("/active/{week_number}")
async def get_active_challenges_for_week(
    week_number: int, current_user: CurrentUser = Depends(require_role("lecturer"))
):
    """Return active challenges for the given week as bundles (challenge + questions).

    Behaviour:
    - Returns at most 2 bundles (one base + optionally one special tier)
    - Each bundle contains the challenge and its questions (5 for base, 1 for special)
    """
    if week_number <= 0:
        raise HTTPException(status_code=400, detail={"error_code": "E_INVALID_WEEK", "message": "week must be > 0"})
    try:
        bundles = await challenge_repository.get_active_for_week(week_number)
        return {"week": week_number, "bundles": bundles}
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error_code": "E_FETCH_FAILED", "message": str(exc)})


# -----------------------------
# Generation helpers
# -----------------------------


async def _resolve_module_code_value(module_code: Optional[str]) -> Optional[str]:
    # Module id was removed from the generation API; if a module_code is provided,
    # just return it. We avoid resolving by id here because endpoints no longer
    # accept module_id.
    return module_code

__all__ = ['router', 'questions_router']
