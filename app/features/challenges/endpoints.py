from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends, Body
from app.common.deps import get_current_user, CurrentUser, require_role
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

router = APIRouter(prefix="/challenges", tags=["challenges"], dependencies=[Depends(get_current_user)])

# ---------------------------------------------
# Lecturer challenge generation
# ---------------------------------------------

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


