import uuid
from typing import List, Optional
from uuid import UUID

from app.DB.supabase import get_supabase
from .schemas import ModuleCreate, ChallengeCreate

# Wrapper like in profiles repo
async def _exec(query):
    result = await query.execute()
    return result.data if result.data else None


class ModuleRepository:

    @staticmethod
    async def create_module(module: ModuleCreate, lecturer_id: int):
        client = await get_supabase()
        data = {
            "id": str(uuid.uuid4()),
            "code": module.code,
            "name": module.name,
            "description": module.description,
            "semester_id": str(module.semester_id),
            "lecturer_id": lecturer_id,
            "code_language": module.code_language,
            "credits": module.credits,
        }
        rows = await _exec(client.table("modules").insert(data))
        return rows[0] if rows else None

    @staticmethod
    async def update_module(module_id: UUID, module: ModuleCreate, lecturer_id: int):
        client = await get_supabase()
        rows = await _exec(
            client.table("modules")
            .update({
                "code": module.code,
                "name": module.name,
                "description": module.description,
                "semester_id": str(module.semester_id),
                "code_language": module.code_language,
                "credits": module.credits,
            })
            .eq("id", str(module_id))
            .eq("lecturer_id", lecturer_id)
        )
        return rows[0] if rows else None

    @staticmethod
    async def delete_module(module_id: UUID, lecturer_id: int):
        client = await get_supabase()
        rows = await _exec(
            client.table("modules")
            .delete()
            .eq("id", str(module_id))
            .eq("lecturer_id", lecturer_id)
        )
        return bool(rows)

    @staticmethod
    async def get_module(module_id: UUID):
        client = await get_supabase()
        rows = await _exec(
            client.table("modules").select("*").eq("id", str(module_id))
        )
        return rows[0] if rows else None

    @staticmethod
    async def list_modules(user):
        client = await get_supabase()
        if user.role.lower() == "lecturer":
            return await _exec(
                client.table("modules").select("*").eq("lecturer_id", user.id)
            ) or []
        else:  # student
            return await _exec(
                client.table("modules")
                .select("*, enrolments!inner(student_id)")
                .eq("enrolments.student_id", user.id)
            ) or []

    @staticmethod
    async def get_students(module_id: UUID, lecturer_id: int):
        client = await get_supabase()
        module = await _exec(
            client.table("modules")
            .select("id")
            .eq("id", str(module_id))
            .eq("lecturer_id", lecturer_id)
        )
        if not module:
            return None
        return await _exec(
            client.table("enrolments")
            .select("student_id, profiles(full_name, email)")
            .eq("module_id", str(module_id))
        ) or []

    @staticmethod
    async def add_challenge(module_id: UUID, challenge: ChallengeCreate, lecturer_id: int):
        client = await get_supabase()
        module = await _exec(
            client.table("modules")
            .select("id")
            .eq("id", str(module_id))
            .eq("lecturer_id", lecturer_id)
        )
        if not module:
            return None
        data = {
            "id": str(uuid.uuid4()),
            "module_id": str(module_id),
            "title": challenge.title,
            "description": challenge.description,
            "max_score": challenge.max_score,
        }
        rows = await _exec(client.table("challenges").insert(data))
        return rows[0] if rows else None

    @staticmethod
    async def get_challenges(module_id: UUID):
        client = await get_supabase()
        return await _exec(
            client.table("challenges").select("*").eq("module_id", str(module_id))
        ) or []

    @staticmethod
    async def is_enrolled(module_id: UUID, student_id: int) -> bool:
        client = await get_supabase()
        rows = await _exec(
            client.table("enrolments")
            .select("id")
            .eq("module_id", str(module_id))
            .eq("student_id", student_id)
        )
        return bool(rows)
