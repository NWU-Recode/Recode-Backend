# admin_panel/endpoints.py
from fastapi import APIRouter, UploadFile, HTTPException, Depends
from typing import List
from uuid import UUID
from .schemas import EnrolmentCreate, EnrolmentBatch, EnrolmentResponse
from .service import AdminService

router = APIRouter(prefix="/admin", tags=["Admin Panel"])
service = AdminService()

# Add single student
@router.post("/students", response_model=EnrolmentResponse)
async def add_student(enrolment: EnrolmentCreate):
    res = await service.add_student(enrolment)
    if not res:
        raise HTTPException(status_code=400, detail="Student already enrolled")
    return res

# Add multiple students from list
@router.post("/students/batch", response_model=List[EnrolmentResponse])
async def add_students_batch(batch: EnrolmentBatch):
    res = await service.add_students_batch(batch)
    if not res:
        raise HTTPException(status_code=400, detail="No students were enrolled")
    return res

# Upload CSV to add students
@router.post("/students/upload-csv", response_model=List[EnrolmentResponse])
async def upload_students_csv(file: UploadFile, module_id: UUID, semester_id: UUID):
    content = await file.read()
    res = await service.add_batch_students_from_csv(content, module_id, semester_id)
    if not res:
        raise HTTPException(status_code=400, detail="CSV processing failed or no students enrolled")
    return res

# List all students
@router.get("/students", response_model=List[EnrolmentResponse])
async def list_students():
    return await service.list_students()
