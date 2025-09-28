from fastapi import APIRouter, Depends, Query
from typing import Optional, List
from datetime import date
from app.features.students.schemas import StudentProfile, ModuleProgress, BadgeInfo, StudentProgress,StudentProfileUpdate
from app.features.students import service, service_analytics, repository_analytics
from app.common.deps import get_current_user, require_lecturer, require_admin, require_role

router = APIRouter(prefix="/student", tags=["Student"], dependencies=[Depends(require_role("student"))])

@router.get("/me", response_model=StudentProfile)
async def student_me(current=Depends(get_current_user)):
    return await service.get_student_profile(current.id)

@router.patch("/me", response_model=StudentProfile)
async def student_update(profile_update: StudentProfileUpdate, current=Depends(get_current_user)):
    updated_profile = await service.update_student_profile(current.id, profile_update)
    return updated_profile

@router.get("/me/modules", response_model=list[ModuleProgress])
async def student_modules(current=Depends(get_current_user)):
    return await service.get_student_modules(current.id)

@router.get("/me/badges", response_model=list[BadgeInfo])
async def student_badges(current=Depends(get_current_user)):
    return await service.get_student_badges(current.id)

@router.get("/me/progress", response_model=dict)
async def student_progress(current=Depends(get_current_user)):
    progress = await service_analytics.compute_student_progress(current.id)
    elo = await service_analytics.compute_elo(current.id)
    progress["elo"] = elo
    return progress

@router.get("/me/analytics")
async def student_analytics(
    current=Depends(get_current_user),
    module_id: Optional[str] = Query(None, description="Filter by module"),
    start_date: Optional[date] = Query(None, description="Start date for analytics"),
    end_date: Optional[date] = Query(None, description="End date for analytics"),
):
    """
    Returns student analytics (submissions, challenges, ELO/GPA) in chart-ready format.
    Optional filters: module_id, start_date, end_date
    """

    # Fetch all student submissions
    submissions = await repository_analytics.fetch_submissions(current.id)
    
    # Optional: filter by module_id
    if module_id:
        submissions = [s for s in submissions if s.get("module_id") == module_id]

    # Optional: filter by date range
    if start_date:
        submissions = [s for s in submissions if s.get("submitted_at") and s["submitted_at"].date() >= start_date]
    if end_date:
        submissions = [s for s in submissions if s.get("submitted_at") and s["submitted_at"].date() <= end_date]

    # Aggregate challenge stats
    total_attempts = len(submissions)
    total_passed = sum(1 for s in submissions if s.get("status_id") == 3)  # assuming 3 = completed
    total_failed = total_attempts - total_passed

    # Optional: group by week for charting
    weekly_stats = {}
    for s in submissions:
        if not s.get("submitted_at"):
            continue
        week = s["submitted_at"].isocalendar()[1]  # ISO week number
        if week not in weekly_stats:
            weekly_stats[week] = {"attempts": 0, "passed": 0, "failed": 0}
        weekly_stats[week]["attempts"] += 1
        if s.get("status_id") == 3:
            weekly_stats[week]["passed"] += 1
        else:
            weekly_stats[week]["failed"] += 1

    # Fetch ELO/GPA
    elo_data = await repository_analytics.fetch_user_elo(current.id)
    elo = elo_data.get("current_elo", 1000)
    gpa = elo_data.get("gpa", 0.0)

    return {
        "total_attempts": total_attempts,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "weekly_stats": weekly_stats,
        "elo": elo,
        "gpa": gpa
    }