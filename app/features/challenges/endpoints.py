from fastapi import APIRouter, HTTPException, Depends
from app.common.deps import get_current_user, CurrentUser
from .schemas import ChallengeSubmitRequest, ChallengeSubmitResponse, GetChallengeAttemptResponse, ChallengeAttemptQuestionStatus
from .service import challenge_service
from app.features.challenges.repository import challenge_repository
from app.features.questions.repository import question_repository

router = APIRouter(prefix="/challenges", tags=["challenges"])

@router.post('/{challenge_id}/submit', response_model=ChallengeSubmitResponse)
async def submit_challenge(challenge_id: str, current_user: CurrentUser = Depends(get_current_user)):
    try:
        from .schemas import ChallengeSubmitRequest
        req = ChallengeSubmitRequest(challenge_id=challenge_id, items=None)
        return await challenge_service.submit(req, str(current_user.id))
    except ValueError as ve:
        msg = str(ve)
        if msg.startswith("challenge_already_submitted"):
            raise HTTPException(status_code=409, detail={"error_code":"E_CONFLICT","message":"challenge_already_submitted"})
        if msg.startswith("challenge_not_configured"):
            raise HTTPException(status_code=409, detail={"error_code":"E_INVALID_STATE","message":msg})
        if msg.startswith("missing_questions:"):
            missing = msg.split(":",1)[1].split(',') if ':' in msg else []
            raise HTTPException(status_code=400, detail={"error_code":"E_INVALID_INPUT","message":"missing_questions","missing_question_ids":missing})
        if msg.startswith("challenge_expired"):
            raise HTTPException(status_code=409, detail={"error_code":"E_CONFLICT","message":"challenge_expired"})
        raise HTTPException(status_code=400, detail={"error_code":"E_INVALID_INPUT","message":msg})
    except Exception as e:
        raise HTTPException(status_code=400, detail={"error_code":"E_UNKNOWN","message":str(e)})

@router.get('/{challenge_id}/attempt', response_model=GetChallengeAttemptResponse)
async def get_challenge_attempt(challenge_id: str, current_user: CurrentUser = Depends(get_current_user)):
    try:
        user_id = str(current_user.id)
        attempt = await challenge_repository.create_or_get_open_attempt(challenge_id, user_id)
        snapshot = attempt.get("snapshot_questions") or []
        latest_attempts = await question_repository.list_latest_attempts_for_challenge(challenge_id, user_id)
        index = {a.get("question_id"): a for a in latest_attempts}
        questions: list[ChallengeAttemptQuestionStatus] = []
        for snap in snapshot:
            qid = snap["question_id"]
            att = index.get(qid)
            if not att:
                questions.append(ChallengeAttemptQuestionStatus(question_id=qid, status="unattempted"))
            else:
                status = "passed" if att.get("is_correct") else "failed"
                questions.append(ChallengeAttemptQuestionStatus(
                    question_id=qid,
                    status=status,
                    last_submitted_at=att.get("updated_at") or att.get("created_at"),
                    token=att.get("judge0_token")
                ))
        return GetChallengeAttemptResponse(
            challenge_attempt_id=attempt["id"],
            challenge_id=attempt["challenge_id"],
            status=attempt.get("status"),
            started_at=attempt.get("started_at"),
            deadline_at=attempt.get("deadline_at"),
            submitted_at=attempt.get("submitted_at"),
            snapshot_question_ids=[s["question_id"] for s in snapshot],
            questions=questions
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail={"error_code":"E_INVALID_INPUT","message":str(e)})
