from typing import List
from uuid import UUID
from app.DB.supabase import get_supabase

class AdminRepository:

    @staticmethod
    async def add_student(enrolment: dict):
        """Add a single enrolment"""
        client = await get_supabase()

        enrolment_serializable = {
            k: str(v) if isinstance(v, UUID) else v
            for k, v in enrolment.items()
        }

        result = await client.table("enrolments").insert(enrolment_serializable).execute()
        return result.data[0] if result.data else None

    @staticmethod
    async def remove_student(enrolment_id: UUID, lecturer_id: int):
        """Remove a student from a module"""
        client = await get_supabase()
        enrolment_id_str = str(enrolment_id)

        result = await client.table("modules") \
            .select("id") \
            .eq("lecturer_id", lecturer_id) \
            .eq("id", enrolment_id_str) \
            .execute()
        if not result.data:
            return None
        delete_res = await client.table("enrolments").delete().eq("id", enrolment_id_str).execute()
        return delete_res.data[0] if delete_res.data else None

    @staticmethod
    async def list_students(lecturer_id: int):
        """List all students enrolled in modules taught by lecturer"""
        client = await get_supabase()
        result = await client.table("enrolments") \
            .select("""
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
            """) \
            .eq("modules.lecturer_id", lecturer_id) \
            .execute()
        return result.data or []
