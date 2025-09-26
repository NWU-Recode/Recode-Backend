from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends, Body
from app.common.deps import get_current_user, CurrentUser
from .schemas import (
    ChallengeSubmitRequest,
    ChallengeSubmitResponse,
    GetChallengeAttemptResponse,
    ChallengeAttemptQuestionStatus,
    ChallengeGenerateRequest,
)
from .service import challenge_service
from app.features.challenges.repository import challenge_repository
from app.features.challenges.challenge_pack_generator import (
    generate_tier_preview,
    generate_and_save_tier,
)
from app.DB.supabase import get_supabase
from app.features.challenges.semester_orchestrator import semester_orchestrator
from typing import Dict, Any, Optional

router = APIRouter(prefix="/challenges", tags=["challenges"])

# ---------------------------------------------
# Lecturer challenge generation
# ---------------------------------------------

ALLOWED_TIERS = {"base", "ruby", "emerald", "diamond"}


@router.post("/generate/{tier}")
async def generate_challenge(
    tier: str,
    payload: ChallengeGenerateRequest = Body(...),
    current_user: CurrentUser = Depends(get_current_user),
):
    if getattr(current_user, "role", "student") != "lecturer":
        raise HTTPException(status_code=403, detail={"error_code": "E_FORBIDDEN", "message": "lecturer_only"})

    tier_key = tier.lower()
    if tier_key == "common":
        tier_key = "base"
    if tier_key not in ALLOWED_TIERS:
        raise HTTPException(status_code=400, detail={"error_code": "E_INVALID_TIER", "message": "invalid tier"})

    resolved_code = await _resolve_module_code_value(payload.module_code, payload.module_id)
    week_number = int(payload.week_number)
    slide_stack_id = payload.slide_stack_id

    if payload.persist:
        try:
            result = await generate_and_save_tier(
                tier_key,
                week_number,
                slide_stack_id=slide_stack_id,
                module_code=resolved_code,
                lecturer_id=int(getattr(current_user, "id", 0) or 0),
            )
        except Exception as exc:
            import traceback, logging
            logging.getLogger(__name__).exception("Failed to generate and save challenge")
            raise HTTPException(status_code=500, detail={"error_code": "E_GENERATION_FAILED", "message": str(exc)})
        challenge_info = result.get("challenge") if isinstance(result, dict) else None
        if isinstance(challenge_info, dict):
            idem = challenge_info.get("idempotency_key")
            if idem:
                result.setdefault("idempotency_key", idem)
        return {"tier": tier_key, "status": "saved", **result}

    preview = await generate_tier_preview(
        tier_key,
        week_number,
        slide_stack_id=slide_stack_id,
        module_code=resolved_code,
    )
    return {"tier": tier_key, "status": "preview", **preview}
@router.post("/publish/{week_number}")
async def publish_week_challenges(week_number: int, current_user: CurrentUser = Depends(get_current_user)):
    if getattr(current_user, "role", "student") != "lecturer":
        raise HTTPException(status_code=403, detail={"error_code":"E_FORBIDDEN","message":"lecturer_only"})
    if week_number <= 0:
        raise HTTPException(status_code=400, detail={"error_code": "E_INVALID_WEEK", "message": "week must be > 0"})
    res = await challenge_repository.publish_for_week(week_number)
    return {"week": week_number, "status": "published", "updated": res.get("updated", 0)}


@router.get("/semester/overview")
async def get_semester_overview(current_user: CurrentUser = Depends(get_current_user)):
    try:
        return await semester_orchestrator.get_release_overview(str(current_user.id))
    except Exception as e:
        raise HTTPException(status_code=400, detail={"error_code":"E_UNKNOWN","message":str(e)})


@router.get("/published/{week_number}")
async def get_published_challenges(week_number: int):
    """Return published challenge bundles for a given week.

    Response: list of { challenge: <challenge row>, questions: [question rows...] }
    For base/plain challenges we return up to 5 questions (snapshot). For other tiers we return 1 question.
    """
    if week_number <= 0:
        raise HTTPException(status_code=400, detail={"error_code": "E_INVALID_WEEK", "message": "week must be > 0"})
    try:
        rows = await challenge_repository.list_published_for_week(week_number)
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error_code": "E_DB_ERROR", "message": str(exc)})

    client = await get_supabase()
    bundles = []
    for ch in rows:
        cid = ch.get("id")
        if not cid:
            continue
        # determine how many questions to fetch
        tier = ch.get("tier") or ch.get("kind")
        # plain challenges (tier stored as 'plain') should return 5 questions snapshot
        limit = 5 if str(tier).lower() in {"plain", "base", "common"} else 1
        try:
            qresp = await client.table("questions").select("*").eq("challenge_id", cid).order("id").limit(limit).execute()
            questions = qresp.data or []
        except Exception:
            questions = []
        bundles.append({"challenge": ch, "questions": questions})
    return bundles


@router.get("/published/{week_number}")
async def get_published_challenges_for_week(week_number: int, current_user: CurrentUser = Depends(get_current_user)):
    """Return all published challenges for the given week as bundles (challenge + questions).

    - plain (base) challenges return up to 5 questions (snapshot)
    - other tiers return a single question per challenge
    """
    if week_number <= 0:
        raise HTTPException(status_code=400, detail={"error_code": "E_INVALID_WEEK", "message": "week must be > 0"})
    try:
        bundles = await challenge_repository.fetch_published_bundles_for_week(week_number)
        return {"week": week_number, "bundles": bundles}
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error_code": "E_FETCH_FAILED", "message": str(exc)})


# -----------------------------
# Generation helpers
# -----------------------------


async def _resolve_module_code_value(module_code: Optional[str], module_id: Optional[int]) -> Optional[str]:
    if module_code:
        return module_code
    if module_id is None:
        return None
    try:
        client = await get_supabase()
        resp = await client.table("modules").select("code").eq("id", module_id).limit(1).execute()
        rows = resp.data or []
        if rows:
            code = rows[0].get("code")
            if code:
                return str(code)
    except Exception:
        pass
    return None


