from fastapi import APIRouter, Depends, HTTPException
from typing import List
from uuid import UUID

from .schemas import (
    ModuleCreate, ModuleResponse,
    ChallengeCreate, ChallengeResponse,
    StudentResponse,
)
from .service import ModuleService
from ...common.deps import (
    require_lecturer_cookie,
    get_current_user_with_refresh,
    CurrentUser,
)

router = APIRouter(prefix="/modules", tags=["Modules"])


# Lecturer: Create module
@router.post("/", response_model=ModuleResponse)
async def create_module(
    module: ModuleCreate,
    user: CurrentUser = Depends(require_lecturer_cookie()),
):
    created = await ModuleService.create_module(module, user.id)
    if not created:
        raise HTTPException(status_code=400, detail="Failed to create module")
    return created


# Lecturer: Update module
@router.put("/{module_id}", response_model=ModuleResponse)
async def update_module(
    module_id: UUID,
    module: ModuleCreate,
    user: CurrentUser = Depends(require_lecturer_cookie()),
):
    updated = await ModuleService.update_module(module_id, module, user.id)
    if not updated:
        raise HTTPException(status_code=404, detail="Module not found or not authorized")
    return updated


# Lecturer: Delete module
@router.delete("/{module_id}")
async def delete_module(
    module_id: UUID,
    user: CurrentUser = Depends(require_lecturer_cookie()),
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



# Lecturer: Add challenge to module
@router.post("/{module_id}/challenges", response_model=ChallengeResponse)
async def add_challenge(
    module_id: UUID,
    challenge: ChallengeCreate,
    user: CurrentUser = Depends(require_lecturer_cookie()),
):
    created = await ModuleService.add_challenge(module_id, challenge, user.id)
    if not created:
        raise HTTPException(status_code=404, detail="Module not found or not authorized")
    return created


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
