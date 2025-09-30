from fastapi import APIRouter, Depends, HTTPException
from typing import List
from uuid import UUID
from fastapi import UploadFile, File
from app.features.semester.schemas import SemesterCreate, SemesterResponse
from app.features.semester.service import SemesterService



from .schemas import (
    ModuleCreate, ModuleResponse,
    ChallengeCreate, ChallengeResponse,
    StudentResponse,
    EnrolRequest, BatchEnrolRequest, AssignLecturerRequest,
    ModuleAdminCreate,LecturerProfileResponse 
)
from .schemas import RemoveLecturerRequest
from .service import ModuleService,LecturerService 
from ...common.deps import (
    require_lecturer,
    get_current_user,
    require_role,
    CurrentUser,
    require_admin,
)
from app.demo.timekeeper import (
    add_demo_week_offset,
    set_demo_week_offset,
    clear_demo_week_offset,
    get_demo_week_offset,
    add_demo_week_offset_for_module,
    set_demo_week_offset_for_module,
    clear_demo_week_offset_for_module,
    get_demo_week_offset_for_module,
)

router = APIRouter(prefix="/admin", tags=["Admin"])

# lecturer only : get current lecturer profile
@router.get(
    "/me",
    response_model=LecturerProfileResponse,
    summary="Get current lecturer profile",
    description="Fetch the authenticated lecturer’s profile info.",
)
async def get_my_profile(user: CurrentUser = Depends(require_lecturer())):
    """Return the profile for the currently authenticated lecturer."""
    profile = await LecturerService.get_lecturer_profile(user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Lecturer profile not found")
    return profile

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
    user: CurrentUser = Depends(require_admin()),
):
    """Create a module. Admin-only.

    Required role: Admin
    """
    # Use admin_create_module so admins can specify lecturer_id in the payload
    created = await ModuleService.admin_create_module(module, user.id)
    if not created:
        raise HTTPException(status_code=400, detail="Failed to create module")
    return created


# Admin: Update module
@router.put("/{module_code}", response_model=ModuleResponse)
async def update_module(module_code: str, module: ModuleCreate, user: CurrentUser = Depends(require_admin())):
    updated = await ModuleService.update_module_by_code(module_code, module, user.id)
    if not updated:
        raise HTTPException(status_code=404, detail="Module not found or not authorized")
    return updated

# Admin: Delete module
@router.delete("/{module_id}", description=(
        "Delete a module by ID. Requires Admin role.\n\n"
        "Returns {deleted: true} when successful."
    ),)
async def delete_module(module_id: UUID, user: CurrentUser = Depends(require_admin())):
    deleted = await ModuleService.delete_module(module_id)
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
async def list_modules(user: CurrentUser = Depends(get_current_user)):
    """List modules for the current user.

    Roles allowed: Student, Lecturer
    """
    return await ModuleService.list_modules(user)


# Student/Lecturer: View module details
@router.get(
    "/{module_code}",
    response_model=ModuleResponse,
    summary="Get module details (Student/Lecturer)",
    description=(
        "Get details for a module. Students must be enrolled to view; Lecturers must be the assigned lecturer.\n"
        "Requires authenticated user."
    ),
)
async def get_module(
    module_code: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Retrieve module details.

    Roles allowed: Student (if enrolled), Lecturer (if assigned)
    """
    module = await ModuleService.get_module_by_code(module_code, user)
    if not module:
        raise HTTPException(status_code=403, detail="Not authorized for this module")
    return module



# Lecturer: See students in their module
@router.get(
    "/{module_code}/students",
    response_model=List[StudentResponse],
    summary="List students in a module (Lecturer)",
    description=(
        "List students enrolled in a module. Requires Lecturer role and that the lecturer is assigned to the module.\n"
        "Returns a list of student profiles (id, full_name, email)."
    ),
)
async def module_students(
    module_code: str,
    user: CurrentUser = Depends(require_lecturer()),  # <--- note the ()
):
    """List students in a module. Lecturer-only.

    Required role: Lecturer
    """
    students = await ModuleService.get_students_by_code(module_code, user.id)
    if not students:
        raise HTTPException(status_code=403, detail="Not authorized for this module")
    return students



# Student/Lecturer: View challenges in a module
@router.get(
    "/{module_code}/challenges",
    response_model=List[ChallengeResponse],
    summary="List challenges in a module (Student/Lecturer)",
    description=(
        "List coding challenges for a module. Students must be enrolled; Lecturers must be assigned.\n"
        "Returns challenge metadata (id, title, max_score, active flag)."
    ),
)
async def module_challenges(
    module_code: str,
    user: CurrentUser = Depends(get_current_user),
):
    """List challenges for a module.

    Roles allowed: Student (if enrolled), Lecturer (if assigned)
    """
    challenges = await ModuleService.get_challenges_by_code(module_code, user)
    if challenges is None:
        raise HTTPException(status_code=403, detail="Not authorized for this module")
    return challenges


# Lecturer-only: enrol a single student into a module
@router.post(
    "/{module_code}/enrol",
    summary="Enrol a student into a module (Lecturer)",
    description=(
        "Enrol a single student into a module. Requires Lecturer role and that the lecturer is assigned to the module.\n"
        "Body: EnrolRequest { student_id: int (profiles.id), semester_id?: uuid, status?: string }.\n"
        "This endpoint is idempotent: existing enrolments are not duplicated."
    ),
)
async def enrol_student(
    module_code: str,
    req: EnrolRequest,
    user: CurrentUser = Depends(require_lecturer()),
):
    """Enrol a student into a module. Lecturer-only.

    Required role: Lecturer
    """
    res = await ModuleService.enrol_student_by_code(module_code, req.student_id, user.id, req.semester_id)
    if res is None:
        raise HTTPException(status_code=403, detail="Not authorized or module not found")
    return res


# Lecturer-only: batch enrol students (JSON list of ids)
@router.post(
    "/{module_code}/enrol/batch",
    summary="Batch enrol students (Lecturer)",
    description=(
        "Batch enrol students by student id list. Requires Lecturer role and module assignment.\n"
        "Body: BatchEnrolRequest { student_ids: [int], semester_id?: uuid }. Returns created/skipped/failed summary."
    ),
)
async def enrol_students_batch(
    module_code: str,
    req: BatchEnrolRequest,
    user: CurrentUser = Depends(require_lecturer()),
):
    """Batch enrol students. Lecturer-only.

    Required role: Lecturer
    """
    res = await ModuleService.enrol_students_batch_by_code(module_code, req.student_ids, user.id, req.semester_id)
    if not res:
        raise HTTPException(status_code=403, detail="Not authorized or module not found")
    return res


# Lecturer-only: upload CSV to batch enrol students. CSV should have header 'student_id' or 'email'.
@router.post(
    "/{module_code}/enrol/upload",
    summary="Upload CSV to batch enrol students (Lecturer)",
    description=(
        "Upload a CSV file with header 'student_id' or 'email' to batch enrol students. Requires Lecturer role.\n"
        "CSV processing is idempotent and will skip already-enrolled students. Returns created/skipped/failed summary."
    ),
)
async def enrol_students_csv(
    module_code: str,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(require_lecturer()),
):
    """Batch enrol students from CSV. Lecturer-only.

    Required role: Lecturer
    """
    content = await file.read()
    result = await ModuleService.enrol_students_csv_by_code(module_code, content, user.id)
    if isinstance(result, dict) and result.get('error'):
        raise HTTPException(status_code=403, detail=result.get('error'))
    return result


# Admin-only: assign a lecturer to a module
@router.post(
    "/{module_code}/assign-lecturer",
    summary="Assign lecturer to module (Admin)",
    description=(
        "Assign a lecturer to a specific module. Requires Admin role.\n"
        "Body: AssignLecturerRequest { lecturer_id: int (profiles.id) }. Returns the updated module."
    ),
)
async def assign_lecturer(
    module_code: str,
    req: AssignLecturerRequest,
    user: CurrentUser = Depends(require_admin()),
):
    """Assign a lecturer to a module. Admin-only.

    Required role: Admin
    """
    # Support module_code flow: if req.module_code provided use new flow
    # prefer explicit path module_code; body may also contain module_code or module_id for backward compatibility
    target_code = req.module_code or module_code
    if target_code:
        res = await ModuleService.assign_lecturer_by_code(target_code, req.lecturer_id, req.module_id)
    else:
        # fallback to id-based assignment if provided in body
        res = await ModuleService.assign_lecturer(req.module_id, req.lecturer_id)
    if res is None:
        raise HTTPException(status_code=404, detail="Module not found")
    return res


# Admin-only: remove lecturer from module
@router.post(
    "/{module_code}/remove-lecturer",
    summary="Remove lecturer from module (Admin)",
    description=(
        "Remove lecturer assignment from a module. Requires Admin role. Returns the updated module record."
    ),
)
async def remove_lecturer(
    module_code: str,
    user: CurrentUser = Depends(require_admin()),
):
    """Remove lecturer assignment. Admin-only.

    Required role: Admin
    """
    # If a module_code query/body is provided by a client in the future, this handler can be extended.
    # prefer module_code flow
    res = await ModuleService.remove_lecturer_by_code(module_code)
    if res is None:
        raise HTTPException(status_code=404, detail="Module not found")
    return res


# Admin: assign lecturer by body (module_code)
@router.post(
    "/assign-lecturer",
    summary="Assign lecturer to module (Admin) by body",
)
async def assign_lecturer_by_body(
    req: AssignLecturerRequest,
    user: CurrentUser = Depends(require_admin()),
):
    if not req.module_code and not req.module_id:
        raise HTTPException(status_code=400, detail="module_code or module_id required")
    if req.module_code:
        res = await ModuleService.assign_lecturer_by_code(req.module_code, req.lecturer_id, req.module_id)
    else:
        res = await ModuleService.assign_lecturer(req.module_id, req.lecturer_id)
    if res is None:
        raise HTTPException(status_code=404, detail="Module not found")
    return res


# Admin: remove lecturer by body (module_code)
@router.post(
    "/remove-lecturer",
    summary="Remove lecturer from module (Admin) by body",
)
async def remove_lecturer_by_body(
    req: RemoveLecturerRequest,
    user: CurrentUser = Depends(require_admin()),
):
    if not req.module_code and not req.module_id:
        raise HTTPException(status_code=400, detail="module_code or module_id required")
    if req.module_code:
        res = await ModuleService.remove_lecturer_by_code(req.module_code)
    else:
        res = await ModuleService.remove_lecturer(req.module_id)
    if res is None:
        raise HTTPException(status_code=404, detail="Module not found")
    return res

# Admin-only: create semester
@router.post("/semesters", response_model=SemesterResponse, summary="Create semester (Admin)")
def admin_create_semester(
    semester: SemesterCreate,
    current_user: CurrentUser = Depends(require_admin()),
):
    """
    Create a new academic semester.
    Only admins can perform this action.
    """
    try:
        created = SemesterService.create_semester(semester)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return created



# ---- Demo time control (Admin-only) ------------------------------------------------
@router.post(
    "/demo/skip",
    summary="Skip demo weeks (Admin)",
    description="Add a positive or negative number of weeks to the demo offset (e.g. {\"delta\": 1} advances one week).",
)
async def demo_skip_weeks(delta: int = 1, module_code: str | None = None, user: CurrentUser = Depends(require_admin())):
    """Adjust the demo week offset by delta weeks. If module_code is provided, adjust only that module."""
    if module_code:
        new = add_demo_week_offset_for_module(module_code, delta)
    else:
        new = add_demo_week_offset(delta)
    return {"offset_weeks": new}


@router.post(
    "/demo/set",
    summary="Set demo week offset (Admin)",
    description="Set the demo offset to an explicit number of weeks (0 = no skip).",
)
async def demo_set_weeks(offset: int = 0, module_code: str | None = None, user: CurrentUser = Depends(require_admin())):
    if module_code:
        new = set_demo_week_offset_for_module(module_code, offset)
        return {"module_code": module_code, "offset_weeks": new}
    new = set_demo_week_offset(offset)
    return {"offset_weeks": new}


@router.delete(
    "/demo/clear",
    summary="Clear demo week offset (Admin)",
    description="Reset demo offset to zero.",
)
async def demo_clear_weeks(module_code: str | None = None, user: CurrentUser = Depends(require_admin())):
    if module_code:
        clear_demo_week_offset_for_module(module_code)
        return {"module_code": module_code, "offset_weeks": get_demo_week_offset_for_module(module_code)}
    clear_demo_week_offset()
    return {"offset_weeks": get_demo_week_offset()}





