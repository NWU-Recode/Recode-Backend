from fastapi import APIRouter
from .schemas import SemesterCreate, SemesterResponse
from .service import SemesterService
from typing import List

router = APIRouter(prefix="/semesters", tags=["Semesters"])

@router.post("/", response_model=SemesterResponse)
async def create_semester(semester: SemesterCreate):
    return await SemesterService.create_semester(semester)

@router.get("/", response_model=List[SemesterResponse])
async def list_semesters():
    return await SemesterService.list_semesters()

@router.get("/current", response_model=SemesterResponse)
async def current_semester():
    return await SemesterService.current_semester()
