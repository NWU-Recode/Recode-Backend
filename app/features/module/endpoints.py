from fastapi import APIRouter
from .schemas import ModuleCreate, ModuleResponse
from .service import ModuleService
from typing import List
from uuid import UUID

router = APIRouter(prefix="/modules", tags=["Modules"])

@router.post("/", response_model=ModuleResponse)
async def create_module(module: ModuleCreate):
    return await ModuleService.create_module(module)

@router.get("/", response_model=List[ModuleResponse])
async def list_modules():
    return await ModuleService.list_modules()

@router.get("/{module_id}/students")
async def module_students(module_id: UUID):
    return await ModuleService.get_students(module_id)

@router.get("/{module_id}/challenges")
async def module_challenges(module_id: UUID):
    return await ModuleService.get_challenges(module_id)

