from .repository import ModuleRepository
from .schemas import ModuleCreate
from uuid import UUID

class ModuleService:

    @staticmethod
    async def create_module(module: ModuleCreate):
        return await ModuleRepository.create_module(module)

    @staticmethod
    async def list_modules():
        return await ModuleRepository.get_all_modules()

    @staticmethod
    async def get_students(module_id: UUID):
        return await ModuleRepository.get_module_students(module_id)

    @staticmethod
    async def get_challenges(module_id: UUID):
        return await ModuleRepository.get_module_challenges(module_id)
