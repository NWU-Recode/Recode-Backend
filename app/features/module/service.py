from typing import List, Optional
from uuid import UUID

from app.common.deps import CurrentUser

from .schemas import (
    ModuleCreate, ModuleResponse,
    ChallengeCreate, ChallengeResponse,
    StudentResponse,
)
from .repository import ModuleRepository


class ModuleService:

    @staticmethod
    async def create_module(module: ModuleCreate, lecturer_id: int) -> Optional[ModuleResponse]:
        module.code = module.code.upper() 
        data = await ModuleRepository.create_module(module, lecturer_id)
        return ModuleResponse(**data) if data else None

    @staticmethod
    async def update_module(module_id: UUID, module: ModuleCreate, lecturer_id: int) -> Optional[ModuleResponse]:
        data = await ModuleRepository.update_module(module_id, module, lecturer_id)
        return ModuleResponse(**data) if data else None

    @staticmethod
    async def delete_module(module_id: UUID, lecturer_id: int) -> bool:
        return await ModuleRepository.delete_module(module_id, lecturer_id)

    @staticmethod
    async def list_modules(user: CurrentUser) -> List[ModuleResponse]:
        modules = await ModuleRepository.list_modules(user)
        return [ModuleResponse(**m) for m in modules]

    @staticmethod
    async def get_module(module_id: UUID, user: CurrentUser) -> Optional[ModuleResponse]:
        module = await ModuleRepository.get_module(module_id)
        if not module:
            return None
        if user.role.lower() == "student":
            enrolled = await ModuleRepository.is_enrolled(module_id, user.id)
            if not enrolled:
                return None
        if user.role.lower() == "lecturer" and module["lecturer_id"] != user.id:
            return None
        return ModuleResponse(**module)

    @staticmethod
    async def get_students(module_id: UUID, lecturer_id: int) -> Optional[List[StudentResponse]]:
        students = await ModuleRepository.get_students(module_id, lecturer_id)
        if not students:
            return None
        return [
            StudentResponse(
                id=s["student_id"],
                full_name=s.get("profiles", {}).get("full_name", ""),
                email=s.get("profiles", {}).get("email", ""),
            )
            for s in students
        ]

    @staticmethod
    async def add_challenge(module_id: UUID, challenge: ChallengeCreate, lecturer_id: int) -> Optional[ChallengeResponse]:
        data = await ModuleRepository.add_challenge(module_id, challenge, lecturer_id)
        return ChallengeResponse(**data) if data else None

    @staticmethod
    async def get_challenges(module_id: UUID, user: CurrentUser) -> Optional[List[ChallengeResponse]]:
        if user.role.lower() == "student":
            enrolled = await ModuleRepository.is_enrolled(module_id, user.id)
            if not enrolled:
                return None
        elif user.role.lower() == "lecturer":
            module = await ModuleRepository.get_module(module_id)
            if not module or module["lecturer_id"] != user.id:
                return None
        challenges = await ModuleRepository.get_challenges(module_id)
        return [ChallengeResponse(**c) for c in challenges]
