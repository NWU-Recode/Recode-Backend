from uuid import UUID
from typing import List, Optional
from app.DB.supabase import get_supabase
from .schemas import ModuleCreate

class ModuleRepository:

    @staticmethod
    async def create_module(module: ModuleCreate):
        supabase = await get_supabase()
        result = await supabase.table("modules").insert(module.dict()).execute()
        return result.data[0]

    @staticmethod
    async def get_modules(lecturer_id: Optional[int] = None):
        supabase = await get_supabase()
        query = supabase.table("modules").select("*")
        if lecturer_id:
            query = query.eq("lecturer_id", lecturer_id)
        result = await query.execute()
        return result.data

    @staticmethod
    async def get_students(module_id: UUID):
        supabase = await get_supabase()
        result = await supabase.table("enrolments") \
            .select("student_id, semester_id, status") \
            .eq("module_id", module_id) \
            .execute()
        return result.data

    @staticmethod
    async def get_challenges(module_id: UUID):
        supabase = await get_supabase()
        result = await supabase.table("challenges") \
            .select("*") \
            .eq("module_id", module_id) \
            .execute()
        return result.data
