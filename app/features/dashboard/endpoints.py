from fastapi import APIRouter, Depends
from app.common.deps import get_current_user, CurrentUser
from .service import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/")
async def get_dashboard(current_user: CurrentUser = Depends(get_current_user)):
    return await dashboard_service.get_dashboard(str(current_user.id))
