#Achievements feature-user achievements,ELO,badges,titles
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from app.common.deps import get_current_user, CurrentUser
from .schemas import (
    EloUpdateRequest, EloResponse,
    BadgeRequest, BadgeResponse,
    BadgeBatchAddRequest, BadgeBatchAddResponse,
    TitleUpdateRequest, TitleResponse, TitleInfo,
    AchievementsResponse,
    CheckAchievementsRequest, CheckAchievementsResponse
)
from .service import achievements_service

router = APIRouter(prefix="/achievements", tags=["achievements"])

def _err(status: int, code: str, message: str):
    return HTTPException(status_code=status, detail={"error_code": code, "message": message})

#get all achievements for a user for achievement dashboard
@router.get("/users/{user_id}", response_model=AchievementsResponse)
async def get_user_achievements(user_id: str, current_user: CurrentUser = Depends(get_current_user)):
    try:
        return await achievements_service.get_achievements(user_id)
    except Exception as e:
        raise _err(400, "E_INVALID_INPUT", str(e))

#ELO Endpoints
#Get users current ELO score
@router.get("/users/{user_id}/elo", response_model=EloResponse)
async def get_elo(user_id: str, current_user: CurrentUser = Depends(get_current_user)):
    try:
        return await achievements_service.get_elo(user_id)
    except Exception as e:
        raise _err(400, "E_INVALID_INPUT", str(e))
#Update ELO after submission
@router.put("/users/{user_id}/elo", response_model=EloResponse)
async def update_elo(user_id: str, req: EloUpdateRequest, current_user: CurrentUser = Depends(get_current_user)):
    try:
        return await achievements_service.update_elo(user_id, req)
    except Exception as e:
        raise _err(400, "E_INVALID_INPUT", str(e))

#Badges Endpoints
#Get all badges that user has earned
@router.get("/users/{user_id}/badges", response_model=List[BadgeResponse])
async def get_badges(user_id: str, current_user: CurrentUser = Depends(get_current_user)):
    try:
        return await achievements_service.get_badges(user_id)
    except Exception as e:
        raise _err(400, "E_INVALID_INPUT", str(e))

#update bagdge list by adding new one
@router.post("/users/{user_id}/badges", response_model=BadgeResponse)
async def add_badge(user_id: str, req: BadgeRequest, current_user: CurrentUser = Depends(get_current_user)):
    try:
        return await achievements_service.add_badge(user_id, req)
    except Exception as e:
        raise _err(400, "E_INVALID_INPUT", str(e))

@router.post("/users/{user_id}/badges/batch", response_model=BadgeBatchAddResponse)
async def add_badges_batch(user_id: str, req: BadgeBatchAddRequest, current_user: CurrentUser = Depends(get_current_user)):
    try:
        return await achievements_service.add_badges_batch(user_id, req)
    except Exception as e:
        raise _err(400, "E_INVALID_INPUT", str(e))
    
#Title Endpoints
#Gets users active title for dashboard
@router.get("/users/{user_id}/title", response_model=TitleInfo)
async def get_title(user_id: str, current_user: CurrentUser = Depends(get_current_user)):
    try:
        return await achievements_service.get_title(user_id)
    except Exception as e:
        raise _err(400, "E_INVALID_INPUT", str(e))
#Update users active title upon trigger
@router.put("/users/{user_id}/title", response_model=TitleResponse)
async def update_title(user_id: str, req: TitleUpdateRequest, current_user: CurrentUser = Depends(get_current_user)):
    try:
        return await achievements_service.check_title_after_elo_update(user_id, req.old_elo)
    except Exception as e:
        raise _err(400, "E_INVALID_INPUT", str(e))

#Central endpoing
#event driven updates and for triggering badge/title unlocks
@router.post("/users/{user_id}/check", response_model=CheckAchievementsResponse)
async def check_achievements(user_id: str, req: CheckAchievementsRequest, current_user: CurrentUser = Depends(get_current_user)):
    """
    Trigger achievements calculation based on user progress or submission events.
    """
    try:
        return await achievements_service.check_achievements(user_id, req)
    except Exception as e:
        raise _err(400, "E_INVALID_INPUT", str(e))
