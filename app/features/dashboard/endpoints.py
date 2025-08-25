from fastapi import APIRouter, Depends, Query, HTTPException, status
from app.common.deps import get_current_user, CurrentUser
from .service import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/")
async def get_dashboard(current_user: CurrentUser = Depends(get_current_user)):
    return await dashboard_service.get_dashboard(str(current_user.id))
    


@router.get("/summary")
async def get_dashboard_summary(current_user: CurrentUser = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource.",
        )

    return await dashboard_service.get_summary()


@router.get("/leaderboard")
async def get_leaderboard(
    limit: int = Query(10, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
):
    return await dashboard_service.get_leaderboard(limit=limit)