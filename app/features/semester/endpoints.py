"""Endpoints for managing semesters."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends

from app.common.deps import (
    CurrentUser,
    get_current_user,
    require_admin,
)

from .schemas import ModuleResponse, SemesterCreate, SemesterResponse
from .service import SemesterService


router = APIRouter(prefix="/semesters", tags=["Semesters"])


@router.post("/", response_model=SemesterResponse)
def create_semester(
    semester: SemesterCreate,
    current_user: CurrentUser = Depends(require_admin()),
) -> SemesterResponse:
    return SemesterService.create_semester(semester)


@router.get("/", response_model=List[SemesterResponse])
def list_semesters() -> List[SemesterResponse]:
    return SemesterService.list_semesters()


@router.get("/current", response_model=SemesterResponse)
def current_semester(
    current_user: CurrentUser = Depends(get_current_user),
) -> SemesterResponse:
    return SemesterService.current_semester()


@router.get("/{semester_id}/modules", response_model=List[ModuleResponse])
async def semester_modules(
    semester_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> List[ModuleResponse]:
    return SemesterService.get_user_modules(semester_id, current_user.id)

