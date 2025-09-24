from fastapi import APIRouter, Depends, UploadFile, HTTPException, Query
from typing import List, Optional
from uuid import UUID
from .schemas import EnrolmentCreate, EnrolmentBatch, EnrolmentResponse, UserRoleUpdate, UserResponse
from .service import AdminPanelService
from app.common.deps import CurrentUser, require_admin, require_lecturer

router = APIRouter(prefix="/admin_panel", tags=["Admin Panel"])
service = AdminPanelService()

# --- Enrol single student ---
@router.post("/students", response_model=EnrolmentResponse)
async def enrol_student(
    request: EnrolmentCreate,
    user: CurrentUser = Depends(require_lecturer())
):
    return await service.enrol_student(request, user.role, user.id)

# --- Batch enrolment ---
@router.post("/students/batch", response_model=List[EnrolmentResponse])
async def enrol_students_batch(
    requests: Optional[List[EnrolmentCreate]] = None,
    file: Optional[UploadFile] = None,
    module_id: Optional[UUID] = Query(None),
    semester_id: Optional[UUID] = Query(None),
    user: CurrentUser = Depends(require_lecturer())
):
    """
    Batch enroll students via either a JSON list or CSV file.
    - If using CSV: provide file, module_id, and semester_id as query params.
    - If using JSON: provide requests (list of EnrolmentCreate objects), no file needed.
    """
    if file:
        # Validate query params for CSV
        if not module_id or not semester_id:
            raise HTTPException(
                status_code=400,
                detail="module_id and semester_id are required when uploading a CSV"
            )
        content = await file.read()
        return await service.add_batch_students_from_csv(
            content, module_id, semester_id, user.role, user.id
        )

    if requests:
        if not isinstance(requests, list) or len(requests) == 0:
            raise HTTPException(
                status_code=400,
                detail="Requests must be a non-empty list of student objects"
            )
        return await service.enrol_students_batch(requests, user.role, user.id)

    raise HTTPException(
        status_code=400,
        detail="Provide either a CSV file or a JSON list of student objects"
    )

# --- Remove student ---
@router.delete("/students/{enrolment_id}")
async def remove_student(
    enrolment_id: UUID,
    module_id: Optional[UUID] = None,
    user: CurrentUser = Depends(require_lecturer())
):
    return await service.remove_student(enrolment_id, module_id, user.role, user.id)

# --- List students ---
@router.get("/students", response_model=List[EnrolmentResponse])
async def list_students(
    module_id: Optional[UUID] = None,
    user: CurrentUser = Depends(require_lecturer())
):
    return await service.list_students(module_id, user.role, user.id)

# --- View module progress ---
@router.get("/modules/{module_id}/progress")
async def module_progress(
    module_id: UUID,
    user: CurrentUser = Depends(require_lecturer())
):
    return await service.get_module_progress(module_id, user.role, user.id)

# --- Manage user roles (Admin only) ---
@router.put("/users/role", response_model=UserResponse)
async def update_user_role(
    request: UserRoleUpdate,
    user: CurrentUser = Depends(require_admin())
):
    return await service.update_user_role(request)

# --- List all users (Admin only) ---
@router.get("/users", response_model=List[UserResponse])
async def list_users(
    user: CurrentUser = Depends(require_admin())
):
    return await service.get_all_users()
