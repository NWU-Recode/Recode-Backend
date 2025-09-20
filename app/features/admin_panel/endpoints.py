from fastapi import APIRouter, Depends, UploadFile, HTTPException
from typing import List, Optional
from uuid import UUID
from .schemas import EnrolmentCreate, EnrolmentBatch, EnrolmentResponse
from .service import AdminPanelService
from app.common.deps import CurrentUser, require_lecturer

router = APIRouter(prefix="/admin_panel", tags=["Admin Panel"])
service = AdminPanelService()


# --- Single student enrolment ---
@router.post("/students", response_model=EnrolmentResponse)
async def enrol_student(
    request: EnrolmentCreate,
    user: CurrentUser = Depends(require_lecturer())
):
    """Lecturer can enrol a single student in their module."""
    return await service.enrol_student(request, user.id)


# --- Batch enrolment (JSON list or CSV file) ---
@router.post("/students/batch", response_model=List[EnrolmentResponse])
async def enrol_students_batch(
    requests: Optional[List[EnrolmentCreate]] = None,
    file: Optional[UploadFile] = None,
    module_id: Optional[UUID] = None,
    semester_id: Optional[UUID] = None,
    user: CurrentUser = Depends(require_lecturer())
):
    """
    Enrol multiple students via:
    - JSON list of EnrolStudentRequest OR
    - CSV file upload
    """
    if file:
        content = await file.read()
        return await service.add_batch_students_from_csv(content, module_id, semester_id, user.id)
    elif requests:
        return await service.enrol_students_batch(requests, user.id)
    else:
        raise HTTPException(status_code=400, detail="Provide either a JSON list or a CSV file")


# --- Remove a student ---
@router.delete("/students/{enrolment_id}")
async def remove_student(
    enrolment_id: UUID,
    user: CurrentUser = Depends(require_lecturer())
):
    """Lecturer can remove a student from their module."""
    return await service.remove_student(enrolment_id, user.id)


# --- List all students for lecturer's modules ---
@router.get("/students", response_model=List[EnrolmentResponse])
async def list_students(user: CurrentUser = Depends(require_lecturer())):
    """List students enrolled in modules taught by the lecturer."""
    return await service.list_students(user.id)


# --- View module progress ---
@router.get("/modules/{module_id}/progress")
async def module_progress(
    module_id: UUID,
    user: CurrentUser = Depends(require_lecturer())
):
    """View progress of students in a specific module."""
    return await service.get_module_progress(module_id, user.id)

