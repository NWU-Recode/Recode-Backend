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

router = APIRouter(prefix="/admin", tags=["Admin"])


# Admin: Create module (for admins only)
@router.post(
    "/",
    response_model=ModuleResponse,
    summary="Create module (Admin)",
    description=(
        "Create a new module. Requires Admin role.\n\n" 
        "Body: ModuleCreate (code, name, description, semester_id, lecturer_id, ...).\n"
        "On success returns the created Module record."
    ),
)
async def create_module(
    module: ModuleCreate,
    user: CurrentUser = Depends(require_admin_cookie()),
):
    """Create a module. Admin-only.

    Required role: Admin
    """
    created = await ModuleService.create_module(module, user.id)
    if not created:
        raise HTTPException(status_code=400, detail="Failed to create module")
    return created


# Admin: Update module
@router.put(
    "/{module_id}",
    response_model=ModuleResponse,
    summary="Update module (Admin)",
    description=(
        "Update module metadata. Requires Admin role.\n\n"
        "Path: module_id (UUID). Body: ModuleCreate-like payload containing updated fields.\n"
        "Returns the updated Module or 404 if not found/authorized."
    ),
)
async def update_module(
    module_id: UUID,
    module: ModuleCreate,
    user: CurrentUser = Depends(require_admin_cookie()),
):
    """Update a module. Admin-only.

    Required role: Admin
    """
    updated = await ModuleService.update_module(module_id, module, user.id)
    if not updated:
        raise HTTPException(status_code=404, detail="Module not found or not authorized")
    return updated


# Admin: Delete module
@router.delete(
    "/{module_id}",
    summary="Delete module (Admin)",
    description=(
        "Delete a module by id. Requires Admin role.\n\n"
        "Returns {deleted: true} when successful."
    ),
)
async def delete_module(
    module_id: UUID,
    user: CurrentUser = Depends(require_admin_cookie()),
):
    """Delete a module. Admin-only.

    Required role: Admin
    """
    deleted = await ModuleService.delete_module(module_id, user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Module not found or not authorized")
    return {"deleted": True}


# Student/Lecturer: List their modules
@router.get(
    "/",
    response_model=List[ModuleResponse],
    summary="List modules (Student or Lecturer)",
    description=(
        "List modules visible to the current user.\n\n"
        "- Students: lists modules they are enrolled in.\n"
        "- Lecturers: lists modules they teach.\n"
        "Requires authenticated user (Student or Lecturer)."
    ),
)
async def list_modules(user: CurrentUser = Depends(get_current_user_with_refresh)):
    """List modules for the current user.

    Roles allowed: Student, Lecturer
    """
    return await ModuleService.list_modules(user)


# Student/Lecturer: View module details
@router.get(
    "/{module_id}",
    response_model=ModuleResponse,
    summary="Get module details (Student/Lecturer)",
    description=(
        "Get details for a module. Students must be enrolled to view; Lecturers must be the assigned lecturer.\n"
        "Requires authenticated user."
    ),
)
async def get_module(
    module_id: UUID,
    user: CurrentUser = Depends(get_current_user_with_refresh),
):
    """Retrieve module details.

    Roles allowed: Student (if enrolled), Lecturer (if assigned)
    """
    module = await ModuleService.get_module(module_id, user)
    if not module:
        raise HTTPException(status_code=403, detail="Not authorized for this module")
    return module



# Lecturer: See students in their module
@router.get(
    "/{module_id}/students",
    response_model=List[StudentResponse],
    summary="List students in a module (Lecturer)",
    description=(
        "List students enrolled in a module. Requires Lecturer role and that the lecturer is assigned to the module.\n"
        "Returns a list of student profiles (id, full_name, email)."
    ),
)
async def module_students(
    module_id: UUID,
    user: CurrentUser = Depends(require_lecturer_cookie()),  # <--- note the ()
):
    """List students in a module. Lecturer-only.

    Required role: Lecturer
    """
    students = await ModuleService.get_students(module_id, user.id)
    if not students:
        raise HTTPException(status_code=403, detail="Not authorized for this module")
    return students



# Student/Lecturer: View challenges in a module
@router.get(
    "/{module_id}/challenges",
    response_model=List[ChallengeResponse],
    summary="List challenges in a module (Student/Lecturer)",
    description=(
        "List coding challenges for a module. Students must be enrolled; Lecturers must be assigned.\n"
        "Returns challenge metadata (id, title, max_score, active flag)."
    ),
)
async def module_challenges(
    module_id: UUID,
    user: CurrentUser = Depends(get_current_user_with_refresh),
):
    """List challenges for a module.

    Roles allowed: Student (if enrolled), Lecturer (if assigned)
    """
    challenges = await ModuleService.get_challenges(module_id, user)
    if challenges is None:
        raise HTTPException(status_code=403, detail="Not authorized for this module")
    return challenges


# Lecturer-only: enrol a single student into a module
@router.post(
    "/{module_id}/enrol",
    summary="Enrol a student into a module (Lecturer)",
    description=(
        "Enrol a single student into a module. Requires Lecturer role and that the lecturer is assigned to the module.\n"
        "Body: EnrolRequest { student_id: int (profiles.id), semester_id?: uuid, status?: string }.\n"
        "This endpoint is idempotent: existing enrolments are not duplicated."
    ),
)
async def enrol_student(
    module_id: UUID,
    req: EnrolRequest,
    user: CurrentUser = Depends(require_lecturer_cookie()),
):
    """Enrol a student into a module. Lecturer-only.

    Required role: Lecturer
    """
    res = await ModuleService.enrol_student(module_id, req.student_id, user.id, req.semester_id)
    if res is None:
        raise HTTPException(status_code=403, detail="Not authorized or module not found")
    return res


# Lecturer-only: batch enrol students (JSON list of ids)
@router.post(
    "/{module_id}/enrol/batch",
    summary="Batch enrol students (Lecturer)",
    description=(
        "Batch enrol students by student id list. Requires Lecturer role and module assignment.\n"
        "Body: BatchEnrolRequest { student_ids: [int], semester_id?: uuid }. Returns created/skipped/failed summary."
    ),
)
async def enrol_students_batch(
    module_id: UUID,
    req: BatchEnrolRequest,
    user: CurrentUser = Depends(require_lecturer_cookie()),
):
    """Batch enrol students. Lecturer-only.

    Required role: Lecturer
    """
    res = await ModuleService.enrol_students_batch(module_id, req.student_ids, user.id, req.semester_id)
    if not res:
        raise HTTPException(status_code=403, detail="Not authorized or module not found")
    return res


# Lecturer-only: upload CSV to batch enrol students. CSV should have header 'student_id' or 'email'.
@router.post(
    "/{module_id}/enrol/upload",
    summary="Upload CSV to batch enrol students (Lecturer)",
    description=(
        "Upload a CSV file with header 'student_id' or 'email' to batch enrol students. Requires Lecturer role.\n"
        "CSV processing is idempotent and will skip already-enrolled students. Returns created/skipped/failed summary."
    ),
)
async def enrol_students_csv(
    module_id: UUID,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(require_lecturer_cookie()),
):
    """Batch enrol students from CSV. Lecturer-only.

    Required role: Lecturer
    """
    content = await file.read()
    result = await ModuleService.enrol_students_csv(module_id, content, user.id)
    if isinstance(result, dict) and result.get('error'):
        raise HTTPException(status_code=403, detail=result.get('error'))
    return result


# Admin-only: assign a lecturer to a module
@router.post(
    "/{module_id}/assign-lecturer",
    summary="Assign lecturer to module (Admin)",
    description=(
        "Assign a lecturer to a specific module. Requires Admin role.\n"
        "Body: AssignLecturerRequest { lecturer_id: int (profiles.id) }. Returns the updated module."
    ),
)
async def assign_lecturer(
    module_id: UUID,
    req: AssignLecturerRequest,
    user: CurrentUser = Depends(require_admin_cookie()),
):
    """Assign a lecturer to a module. Admin-only.

    Required role: Admin
    """
    res = await ModuleService.assign_lecturer(module_id, req.lecturer_id)
    if res is None:
        raise HTTPException(status_code=404, detail="Module not found")
    return res


# Admin-only: remove lecturer from module
@router.post(
    "/{module_id}/remove-lecturer",
    summary="Remove lecturer from module (Admin)",
    description=(
        "Remove lecturer assignment from a module. Requires Admin role. Returns the updated module record."
    ),
)
async def remove_lecturer(
    module_id: UUID,
    user: CurrentUser = Depends(require_admin_cookie()),
):
    """Remove lecturer assignment. Admin-only.

    Required role: Admin
    """
    res = await ModuleService.remove_lecturer(module_id)
    if res is None:
        raise HTTPException(status_code=404, detail="Module not found")
    return res


# Admin-only: create semester
@router.post(
    "/semesters",
    response_model=dict,
    summary="Create semester (Admin)",
    description=(
        "Create a new academic semester. Requires Admin role.\n\n"
        "Body: SemesterCreate { year, term_name, start_date, end_date, is_current }.\n"
        "If is_current is true this semester will be considered the current active semester."
    ),
)
async def create_semester(
    payload: SemesterCreate,
    user: CurrentUser = Depends(require_admin_cookie()),
):
    """Create a semester. Admin-only.

    Required role: Admin
    """
    created = await ModuleService.create_semester(payload.year, payload.term_name, payload.start_date, payload.end_date, payload.is_current)
    if not created:
        raise HTTPException(status_code=400, detail="Failed to create semester")
    return created


# Admin-only: create module (allows passing semester_id or uses current semester)
@router.post(
    "/modules",
    response_model=ModuleResponse,
    summary="Create module for semester (Admin)",
    description=(
        "Create a new module for a given semester. Requires Admin role.\n\n"
        "If semester_id is not provided, the current semester will be used (if set).\n"
        "Body: ModuleAdminCreate { code, name, description, semester_id?, lecturer_id, ... }."
    ),
)
async def admin_create_module(
    payload: ModuleAdminCreate,
    user: CurrentUser = Depends(require_admin_cookie()),
):
    """Create a module for a semester. Admin-only.

    Required role: Admin
    """
    # If semester_id not provided, look up current semester
    semester_id = payload.semester_id
    if not semester_id:
        curr = await ModuleService.get_current_semester()
        if curr:
            semester_id = curr.get("id")
        else:
            raise HTTPException(status_code=400, detail="No semester provided and no current semester set")

    # build admin payload with resolved semester
    payload.semester_id = semester_id
    created = await ModuleService.admin_create_module(payload, user.id)
    if not created:
        raise HTTPException(status_code=400, detail="Failed to create module")
    return created
