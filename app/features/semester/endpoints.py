from fastapi import APIRouter, Depends
from typing import List
from .schemas import SemesterCreate, SemesterResponse, ModuleResponse
from .service import SemesterService
from app.common.deps import get_current_user, require_admin, CurrentUser

router = APIRouter(prefix="/semesters", tags=["Semesters"])

# Admin-only: create semester
@router.post("/", response_model=SemesterResponse)
def create_semester(
    semester: SemesterCreate,
    current_user: CurrentUser = Depends(require_admin)
):
    return SemesterService.create_semester(semester)

# Everyone: list semesters
@router.get("/", response_model=List[SemesterResponse])
def list_semesters():
    return SemesterService.list_semesters()  # Service handles DB session

# Everyone: get current semester
@router.get("/current", response_model=SemesterResponse)
def current_semester(current_user: CurrentUser = Depends(get_current_user)):
    return SemesterService.current_semester()

# Students: get modules for a semester
@router.get("/semesters/{semester_id}/modules", response_model=List[ModuleResponse])
async def semester_modules(semester_id: str, current_user: str = Depends(get_current_user)):
    return SemesterService.get_user_modules(semester_id, current_user.id)