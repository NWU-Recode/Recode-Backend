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

    @staticmethod
    async def get_profile_by_email(email: str) -> Optional[dict]:
        client = await get_supabase()
        rows = await _exec(client.table("profiles").select("id, full_name, email").eq("email", email).limit(1))
        return rows[0] if rows else None

    @staticmethod
    async def add_enrolment_if_not_exists(module_id: UUID, student_id: int, semester_id: Optional[UUID] = None, status: str = "active") -> dict:
        # Check existing enrolment first (idempotent)
        exists = await ModuleRepository.is_enrolled(module_id, student_id)
        if exists:
            return {"created": False, "reason": "already_enrolled", "student_id": student_id}
        client = await get_supabase()
        data = {"module_id": str(module_id), "student_id": student_id, "status": status}
        if semester_id:
            data["semester_id"] = str(semester_id)
        rows = await _exec(client.table("enrolments").insert(data))
        if rows:
            return {"created": True, "row": rows[0]}
        return {"created": False, "reason": "insert_failed", "student_id": student_id}

    @staticmethod
    async def add_enrolment(module_id: UUID, student_id: int, semester_id: Optional[UUID] = None, status: str = "active") -> Optional[dict]:
        client = await get_supabase()
        data = {
            "module_id": str(module_id),
            "student_id": student_id,
            "status": status,
        }
        if semester_id:
            data["semester_id"] = str(semester_id)
        rows = await _exec(client.table("enrolments").insert(data))
        return rows[0] if rows else None

    @staticmethod
    async def add_enrolments_batch(module_id: UUID, student_ids: List[int], semester_id: Optional[UUID] = None, status: str = "active") -> dict:
        """
        Idempotent batch enrolment: for each student, try add_enrolment_if_not_exists.
        Returns a summary dict with created/skipped/failed lists for transparency.
        """
        created = []
        skipped = []
        failed = []
        for sid in student_ids:
            try:
                res = await ModuleRepository.add_enrolment_if_not_exists(module_id, sid, semester_id, status)
                if res.get("created"):
                    created.append(res.get("row") or {"student_id": sid})
                else:
                    skipped.append({"student_id": sid, "reason": res.get("reason")})
            except Exception as e:
                failed.append({"student_id": sid, "error": str(e)})
        return {"created": created, "skipped": skipped, "failed": failed}

    @staticmethod
    async def assign_lecturer(module_id: UUID, lecturer_profile_id: int) -> Optional[dict]:
        client = await get_supabase()
        rows = await _exec(client.table("modules").update({"lecturer_id": lecturer_profile_id}).eq("id", str(module_id)))
        return rows[0] if rows else None

    @staticmethod
    async def remove_lecturer(module_id: UUID) -> Optional[dict]:
        client = await get_supabase()
        rows = await _exec(client.table("modules").update({"lecturer_id": None}).eq("id", str(module_id)))
        return rows[0] if rows else None

    # -------------------
    # Semester helpers
    # -------------------
    @staticmethod
    async def create_semester(year: int, term_name: str, start_date, end_date, is_current: bool = False) -> Optional[dict]:
        client = await get_supabase()
        data = {
            "year": year,
            "term_name": term_name,
            "start_date": start_date,
            "end_date": end_date,
            "is_current": is_current,
        }
        rows = await _exec(client.table("semesters").insert(data))
        return rows[0] if rows else None

    @staticmethod
    async def get_current_semester() -> Optional[dict]:
        client = await get_supabase()
        rows = await _exec(client.table("semesters").select("*").eq("is_current", True).limit(1))
        return rows[0] if rows else None

    @staticmethod
    async def get_semester_by_id(semester_id: UUID) -> Optional[dict]:
        client = await get_supabase()
        rows = await _exec(client.table("semesters").select("*").eq("id", str(semester_id)).limit(1))
        return rows[0] if rows else None
    
class LecturerRepository:
    @staticmethod
    async def get_lecturer_by_id(lecturer_id: str) -> Optional[dict]:
        client = await get_supabase()
        rows = await _exec(
            client.table("profiles")
            .select("id, full_name, email, avatar_url, phone, bio")
            .eq("id", str(lecturer_id))
            .limit(1)
        )
        return rows[0] if rows else None

