from fastapi import APIRouter, Depends
from app.features.students.schemas import (
    StudentProfile,
    StudentProfileUpdate,
    ModuleProgress,
    BadgeInfo,
    StudentProgress,
)
from app.features.students import service, service_analytics, repository_analytics
from app.common.deps import require_student, require_role
from app.features.students import service, service_analytics
from app.common.deps import require_student

router = APIRouter(prefix="/student", tags=["Student"], dependencies=[Depends(require_role("student"))])

@router.get("/me", response_model=StudentProfile)
async def student_me(current=Depends(require_student())):
    return await service.get_student_profile(current.id)

@router.patch("/me", response_model=StudentProfile)
async def student_update(
    profile_update: StudentProfileUpdate,
    current=Depends(require_student()),
):
    return await service.update_student_profile(current.id, profile_update)

@router.get("/me/modules", response_model=list[ModuleProgress])
async def student_modules(current=Depends(require_student())):
    return await service.get_student_modules(current.id)

@router.get("/me/badges", response_model=list[BadgeInfo])
async def student_badges(current=Depends(require_student())):
    return await service.get_student_badges(current.id)

@router.get("/me/progress", response_model=StudentProgress)
async def student_progress(current=Depends(require_student())):
    return await service_analytics.get_full_student_progress(current.id)

@router.get("/me/analytics", response_model=dict)
async def student_analytics(current=Depends(require_student())):
    return await service_analytics.compute_student_analytics(current.id)
