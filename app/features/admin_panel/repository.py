from typing import List
from uuid import UUID
from app.DB.supabase import get_supabase

class AdminRepository:

    @staticmethod
    async def add_student(enrolment: dict):
        client = await get_supabase()
        enrolment_serializable = {
            k: str(v) if isinstance(v, UUID) else v
            for k, v in enrolment.items()
        }
        result = await client.table("enrolments").insert(enrolment_serializable).execute()
        return result.data[0] if result.data else None

    @staticmethod
    async def remove_student(enrolment_id: UUID, module_id: UUID = None, user_role: str = "lecturer", user_id: int = None):
        client = await get_supabase()
        enrolment_id_str = str(enrolment_id)

        # Lecturers can only remove from their own modules
        query = client.table("enrolments").delete().eq("id", enrolment_id_str)
        if user_role.lower() == "lecturer" and module_id:
            query = query.eq("module_id", str(module_id))
        result = await query.execute()
        return result.data[0] if result.data else None

    @staticmethod
    async def list_students(module_id: UUID = None, user_role: str = "lecturer", user_id: int = None):
        client = await get_supabase()
        query = client.table("enrolments").select(
            """
            id,
            module_id,
            semester_id,
            enrolled_on,
            status,
            profiles!inner(
                id,
                supabase_id,
                full_name,
                email,
                role,
                avatar_url,
                phone
            ),
            modules!inner(
                id,
                name,
                code,
                lecturer_id
            )
            """
        )
        if user_role.lower() == "lecturer":
            query = query.eq("modules.lecturer_id", user_id)
        elif module_id:
            query = query.eq("module_id", str(module_id))
        result = await query.execute()
        return result.data or []

    @staticmethod
    async def update_user_role(user_id: int, new_role: str):
        client = await get_supabase()
        result = await client.table("profiles").update({"role": new_role}).eq("id", user_id).execute()
        return result.data[0] if result.data else None

    @staticmethod
    async def get_all_users():
        client = await get_supabase()
        result = await client.table("profiles").select("*").execute()
        return result.data or []
