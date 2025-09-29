from fastapi import APIRouter, Depends, HTTPException
from typing import List
from uuid import UUID
from fastapi import UploadFile, File

from .schemas import (
    ModuleCreate, ModuleResponse,
    ChallengeCreate, ChallengeResponse,
    StudentResponse,
    EnrolRequest, BatchEnrolRequest, AssignLecturerRequest,
    SemesterCreate, ModuleAdminCreate,
)
from .service import ModuleService
from ...common.deps import (
    require_lecturer_cookie,
    get_current_user_with_refresh,
    CurrentUser,
    require_admin_cookie,
)

router = APIRouter(prefix="/modules", tags=["Modules"])


# Admin: Create module (moved to admin prefix below as well but keep explicit admin route)
@router.post("/", response_model=ModuleResponse)
async def create_module(
    module: ModuleCreate,
    user: CurrentUser = Depends(require_admin_cookie()),
):
    created = await ModuleService.create_module(module, user.id)
    if not created:
        raise HTTPException(status_code=400, detail="Failed to create module")
    return created


# Admin: Update module
@router.put("/{module_id}", response_model=ModuleResponse)
async def update_module(
    module_id: UUID,
    module: ModuleCreate,
    user: CurrentUser = Depends(require_admin_cookie()),
):
    updated = await ModuleService.update_module(module_id, module, user.id)
    if not updated:
        raise HTTPException(status_code=404, detail="Module not found or not authorized")
    return updated


# Admin: Delete module
@router.delete("/{module_id}")
async def delete_module(
    module_id: UUID,
    user: CurrentUser = Depends(require_admin_cookie()),
):
    deleted = await ModuleService.delete_module(module_id, user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Module not found or not authorized")
    return {"deleted": True}


# Student/Lecturer: List their modules
@router.get("/", response_model=List[ModuleResponse])
async def list_modules(user: CurrentUser = Depends(get_current_user_with_refresh)):
    return await ModuleService.list_modules(user)


# Student/Lecturer: View module details
@router.get("/{module_id}", response_model=ModuleResponse)
async def get_module(
    module_id: UUID,
    user: CurrentUser = Depends(get_current_user_with_refresh),
):
    module = await ModuleService.get_module(module_id, user)
    if not module:
        raise HTTPException(status_code=403, detail="Not authorized for this module")
    return module


# Lecturer: See students in their module
@router.get("/{module_id}/students", response_model=List[StudentResponse])
async def module_students(
    module_id: UUID,
    user: CurrentUser = Depends(require_lecturer_cookie()),  # <--- note the ()
):
    students = await ModuleService.get_students(module_id, user.id)
    if not students:
        raise HTTPException(status_code=403, detail="Not authorized for this module")
    return students



# Student/Lecturer: View challenges in a module
@router.get("/{module_id}/challenges", response_model=List[ChallengeResponse])
async def module_challenges(
    module_id: UUID,
    user: CurrentUser = Depends(get_current_user_with_refresh),
):
    challenges = await ModuleService.get_challenges(module_id, user)
    if challenges is None:
        raise HTTPException(status_code=403, detail="Not authorized for this module")
    return challenges


# Lecturer-only: enrol a single student into a module
@router.post("/{module_id}/enrol")
async def enrol_student(
    module_id: UUID,
    req: EnrolRequest,
    user: CurrentUser = Depends(require_lecturer_cookie()),
):
    res = await ModuleService.enrol_student(module_id, req.student_id, user.id, req.semester_id)
    if res is None:
        raise HTTPException(status_code=403, detail="Not authorized or module not found")
    return res


# Lecturer-only: batch enrol students (JSON list of ids)
@router.post("/{module_id}/enrol/batch")
async def enrol_students_batch(
    module_id: UUID,
    req: BatchEnrolRequest,
    user: CurrentUser = Depends(require_lecturer_cookie()),
):
    res = await ModuleService.enrol_students_batch(module_id, req.student_ids, user.id, req.semester_id)
    if not res:
        raise HTTPException(status_code=403, detail="Not authorized or module not found")
    return {"created": len(res), "rows": res}


# Lecturer-only: upload CSV to batch enrol students. CSV should have header 'student_id' or 'email'.
@router.post("/{module_id}/enrol/upload")
async def enrol_students_csv(
    module_id: UUID,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(require_lecturer_cookie()),
):
    content = await file.read()
    result = await ModuleService.enrol_students_csv(module_id, content, user.id)
    if isinstance(result, dict) and result.get('error'):
        raise HTTPException(status_code=403, detail=result.get('error'))
    return result


# Admin-only: assign a lecturer to a module
@router.post("/{module_id}/assign-lecturer")
async def assign_lecturer(
    module_id: UUID,
    req: AssignLecturerRequest,
    user: CurrentUser = Depends(require_admin_cookie()),
):
    # Support new flow: callers may provide module_code in body instead of module_id
    target_module = req.module_id or module_id
    res = None
    if req.module_code:
        res = await ModuleService.assign_lecturer_by_code(req.module_code, req.lecturer_id, req.module_id)
    else:
        res = await ModuleService.assign_lecturer(target_module, req.lecturer_id)
    if res is None:
        raise HTTPException(status_code=404, detail="Module not found")
    return res


# Admin-only: remove lecturer from module
@router.post("/{module_id}/remove-lecturer")
async def remove_lecturer(
    module_id: UUID,
    user: CurrentUser = Depends(require_admin_cookie()),
):
    # Support removing by module_code via query param 'module_code'
    # module_id path param kept for backward compatibility
    module_code = None
    # FastAPI will put query params into function kwargs only if declared; try to read from request via header? Keep simple: prefer module_id path
    res = await ModuleService.remove_lecturer(module_id)
    if res is None:
        raise HTTPException(status_code=404, detail="Module not found")
    return res


# Admin routes for semesters/modules are defined under app.features.admin.endpoints
