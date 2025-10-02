from fastapi import APIRouter, Depends, HTTPException
from app.common.deps import get_current_user, CurrentUser
from .service import dashboard_service
from .service import *
from .schema import *
from app.DB.session import get_db
from datetime import date, datetime


router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/current-week", response_model=CurrentWeekResponse)
def get_current_week(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the current week number in the active semester."""
    return current_week_service(db)

@router.get("/")
async def get_dashboard(current_user: CurrentUser = Depends(get_current_user)):
    return await dashboard_service.get_dashboard(str(current_user.id))

@router.get("/student/dashboard", response_model=StudentDashboardOut)
def student_dashboard(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    row = student_dashboard_service(current_user.id, db)  # remove .first()
    
    if not row:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    
    data = dict(row._mapping)  # convert Row to dict
    return data

