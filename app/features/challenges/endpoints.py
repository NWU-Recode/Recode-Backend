from fastapi import APIRouter, HTTPException, Depends, Body
from app.common.deps import get_current_user, CurrentUser
from .schemas import ChallengeSubmitRequest, ChallengeSubmitResponse, GetChallengeAttemptResponse, ChallengeAttemptQuestionStatus
from .service import challenge_service
from app.features.challenges.repository import challenge_repository
from app.features.topic_detections.repository import question_repository 
from app.features.challenges.generation import generate_week_challenges
from app.features.slides.pathing import parse_week_topic_from_filename
import re

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


# -----------------------------
# GENERATION (moved from weeks)
# -----------------------------
class _GenerateReq:
    def __init__(self, slides_url: str, force: bool = False):
        self.slides_url = slides_url
        self.force = force


@router.post("/create")
async def create_from_slides(req: dict = Body(...)):
    try:
        gr = _GenerateReq(slides_url=req.get("slides_url"), force=bool(req.get("force", False)))
        if not isinstance(gr.slides_url, str) or not gr.slides_url:
            raise HTTPException(status_code=400, detail={"error_code":"E_INVALID_INPUT","message":"slides_url required"})
        week_number = None
        m = re.search(r"/w(\d{2})/", gr.slides_url)
        if m:
            try:
                week_number = int(m.group(1))
            except Exception:
                week_number = None
        if week_number is None:
            # Try to extract from filename
            if gr.slides_url.startswith("supabase://"):
                rest = gr.slides_url.split("://", 1)[1]
                parts = rest.split("/", 1)
                object_key = parts[1] if len(parts) == 2 else parts[0]
                filename = object_key.split("/")[-1]
            else:
                filename = gr.slides_url.split("/")[-1]
            derived, _ = parse_week_topic_from_filename(filename)
            if derived:
                week_number = int(derived)
        if not week_number:
            raise HTTPException(status_code=400, detail={
                "error_code": "E_INVALID_INPUT",
                "message": "Could not derive week from slides_url. Include /wNN/ in path or use filename 'Week{n}_...'."
            })
        return await generate_week_challenges(week_number, gr.slides_url, gr.force)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"error_code":"E_UNKNOWN","message":str(e)})


@router.post("/{week_number}/create")
async def create_for_week(week_number: int, req: dict = Body(...)):
    if week_number <= 0:
        raise HTTPException(status_code=400, detail={"error_code": "E_INVALID_WEEK", "message": "week must be > 0"})
    slides_url = req.get("slides_url")
    force = bool(req.get("force", False))
    if not slides_url:
        raise HTTPException(status_code=400, detail={"error_code":"E_INVALID_INPUT","message":"slides_url required"})
    return await generate_week_challenges(week_number, slides_url, force)


@router.post("/publish/{week_number}")
async def publish_week_challenges(week_number: int):
    if week_number <= 0:
        raise HTTPException(status_code=400, detail={"error_code": "E_INVALID_WEEK", "message": "week must be > 0"})
    return {"week": week_number, "status": "published"}
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional, Dict, Any
from .service import generate_week
from app.features.slides.pathing import parse_week_topic_from_filename
import re


router = APIRouter(prefix="/weeks", tags=["weeks"])


class GenerateRequest(BaseModel):
    slides_url: str
    force: bool = False


@router.post("/generate")
async def generate_week_auto(req: GenerateRequest):
    """Generate a week from slides without specifying week in the path.

    Derives week from slides_url (e.g., supabase://slides/.../w03/...) or from
    the filename (e.g., Week3_Conditionals.pptx). Fails if no week can be found.
    """
    week_number: Optional[int] = None
    # Try to extract /wNN/ from the path
    m = re.search(r"/w(\d{2})/", req.slides_url)
    if m:
        try:
            week_number = int(m.group(1))
        except Exception:
            week_number = None
    if week_number is None:
        # Fallback: last path segment filename
        path_part = req.slides_url
        if req.slides_url.startswith("supabase://"):
            # supabase://<bucket>/<object_key>
            rest = req.slides_url.split("://", 1)[1]
            parts = rest.split("/", 1)
            object_key = parts[1] if len(parts) == 2 else parts[0]
            filename = object_key.split("/")[-1]
        else:
            filename = req.slides_url.split("/")[-1]
        derived, _ = parse_week_topic_from_filename(filename)
        if derived:
            week_number = int(derived)
    if not week_number:
        raise HTTPException(status_code=400, detail={
            "error_code": "E_INVALID_INPUT",
            "message": "Could not derive week from slides_url. Include /wNN/ in the path or use filename 'Week{n}_...'."
        })
    return await generate_week(week_number, req.slides_url, req.force)


@router.post("/{week_number}/generate")
async def generate_week_endpoint(week_number: int, req: GenerateRequest):
    """Generate a week from slides (scaffold).

    Returns a minimal payload consistent with the smoke test expectations.
    """
    if week_number <= 0:
        raise HTTPException(status_code=400, detail={"error_code": "E_INVALID_WEEK", "message": "week must be > 0"})

    # Delegate to service orchestrator
    result = await generate_week(week_number, req.slides_url, req.force)
    return result


@router.post("/{week_number}/publish")
async def publish_week(week_number: int):
    if week_number <= 0:
        raise HTTPException(status_code=400, detail={"error_code": "E_INVALID_WEEK", "message": "week must be > 0"})
    return {"week": week_number, "status": "published"}
 #week needs to be replaced by  challenge here note
