from fastapi import HTTPException, status
import uuid 
from datetime import datetime, date
from typing import List, Optional 
from uuid import UUID
from app.DB.supabase import get_supabase
import uuid
from .schemas import ModuleCreate, ChallengeCreate

# Wrapper like in profiles repo
async def _exec(query):
    result = await query.execute()
    return result.data if result.data else None


class ModuleRepository:

    @staticmethod
    async def create_module(module_data: ModuleCreate, admin_id: int):
        client = await get_supabase()

    # Check if lecturer exists
        lecturer_request = client.table("lecturers").select("*").eq("profile_id", module_data.lecturer_id).maybe_single()
        lecturer_result = await lecturer_request.execute()
        lecturer = lecturer_result.data
        if not lecturer:
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Lecturer with id {module_data.lecturer_id} does not exist."
        )

    # If lecturer exists, insert module
        data = {
        "code": module_data.code,
        "name": module_data.name,
        "description": module_data.description,
        "semester_id": str(module_data.semester_id),
        "lecturer_id": module_data.lecturer_id,
        "code_language": module_data.code_language,
        "credits": module_data.credits,
    }
        rows = await _exec(client.table("modules").insert(data))
        return rows[0] if rows else None

    @staticmethod
    async def update_module(module_id: UUID, module: ModuleCreate, admin_id: int):
     client = await get_supabase()

    # ✅ Validate lecturer if provided
     if module.lecturer_id:
        lecturer_result = await client.table("lecturers") \
            .select("*") \
            .eq("profile_id", module.lecturer_id) \
            .maybe_single() \
            .execute()
        if not lecturer_result.data:
            raise HTTPException(
                status_code=400,
                detail=f"Lecturer with id {module.lecturer_id} does not exist."
            )

    # ✅ Build update data
     data = {
        "code": module.code,
        "name": module.name,
        "description": module.description,
        "semester_id": str(module.semester_id),
        "code_language": module.code_language,
        "credits": module.credits,
    }

    # Include lecturer_id only if provided
     if module.lecturer_id:
        data["lecturer_id"] = module.lecturer_id

    # ✅ Execute update
     rows = await _exec(
        client.table("modules")
        .update(data)
        .eq("id", str(module_id))
    )

     return rows[0] if rows else None




    # Repository
    @staticmethod
    async def delete_module(module_id: UUID) -> bool:
     client = await get_supabase()
     rows = await _exec(client.table("modules").delete().eq("id", str(module_id)))
     return bool(rows)


    @staticmethod
    async def get_module(module_id: UUID):
            client = await get_supabase()
            rows = await _exec(
                client.table("modules").select("*").eq("id", str(module_id))
            )
            return rows[0] if rows else None

    @staticmethod
    async def get_module_by_code(module_code: str):
        client = await get_supabase()
        rows = await _exec(
            client.table("modules").select("*").eq("code", str(module_code)).limit(1)
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
    async def add_challenge(module_code: str, challenge: ChallengeCreate, lecturer_id: int):
        client = await get_supabase()
        module = await _exec(
            client.table("modules")
            .select("code, lecturer_id")
            .eq("code", module_code)
            .eq("lecturer_id", lecturer_id)
        )
        if not module:
            return None
        data = {
            "id": str(uuid.uuid4()),
            "module_code": module_code,
            "title": challenge.title,
            "description": challenge.description,
            "max_score": challenge.max_score,
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
        rows = await _exec(client.table("challenges").insert(data))
        return rows[0] if rows else None

    @staticmethod
    async def get_challenges(module_code: str):
        client = await get_supabase()
        res = await _exec(
            client.table("challenges").select("*").eq("module_code", module_code)
        )
        return res or []


    @staticmethod
    async def is_enrolled(module_id: UUID, student_id: int) -> bool:
        client = await get_supabase()
        rows = await _exec(
            client.table("enrolments")
            .select("id")
            .eq("module_id", module_id)
            .eq("student_id", student_id)
        )
        return bool(rows)

    @staticmethod
    async def get_profile_by_email(email: str) -> Optional[dict]:
        client = await get_supabase()
        rows = await _exec(client.table("profiles").select("id, full_name, email").eq("email", email).limit(1))
        return rows[0] if rows else None

    @staticmethod
    async def add_enrolment_if_not_exists(module_id: UUID,student_number: int, semester_id: Optional[UUID] = None, status: str = "active") -> dict:
        # Check existing enrolment first (idempotent)
       # Check if student is already enrolled
        exists = await ModuleRepository.is_enrolled(module_id, student_number)
        if exists:
            return {"created": False, "reason": "already_enrolled", "student_id": student_number}

        # Reuse add_enrolment to insert and handle UUID conversions
        row = await ModuleRepository.add_enrolment(module_id, student_number, semester_id, status)
        if row:
            return {"created": True, "row": row}

        return {"created": False, "reason": "insert_failed", "student_number": student_number}
    
    @staticmethod
    async def add_enrolment(module_id: UUID, student_number: int, semester_id: Optional[UUID] = None, status: str = "active") -> Optional[dict]:
        client = await get_supabase()
        data = {
            "module_id": str(module_id),
            "student_number": student_number,
            "status": status,
        }
        if semester_id:
            data["semester_id"] = str(semester_id)

        rows = await _exec(client.table("enrolments").insert(data))
        if not rows:
            return None

        # Convert UUIDs in the returned row to strings for JSON safety
        row = rows[0]
        for k, v in row.items():
            if isinstance(v, UUID):
                row[k] = str(v)
        return row

    @staticmethod
    async def add_enrolments_batch(module_id: UUID, student_numbers: List[int], semester_id: Optional[UUID] = None, status: str = "active") -> dict:
        """
        Idempotent batch enrolment: for each student, try add_enrolment_if_not_exists.
        Returns a summary dict with created/skipped/failed lists for transparency.
        """
        created = []
        skipped = []
        failed = []
        for sn in student_numbers:
            try:
                res = await ModuleRepository.add_enrolment_if_not_exists(module_id, sn, semester_id, status)
                if res.get("created"):
                    created.append(res.get("row") or {"student_number": sn})
                else:
                    skipped.append({"student_number": sn, "reason": res.get("reason")})
            except Exception as e:
                failed.append({"student_number": sn, "error": str(e)})
        return {"created": created, "skipped": skipped, "failed": failed}

    @staticmethod
    async def assign_lecturer(module_id: UUID, lecturer_profile_id: int) -> Optional[dict]:
        client = await get_supabase()
        rows = await _exec(client.table("modules").update({"lecturer_id": lecturer_profile_id}).eq("id", str(module_id)))
        return rows[0] if rows else None

    @staticmethod
    async def assign_lecturer_by_code(module_code: str, lecturer_profile_id: int, fallback_module_id: Optional[UUID] = None) -> Optional[dict]:
        client = await get_supabase()
        # Find module by code
        rows = await _exec(client.table("modules").select("id, semester_id").eq("code", str(module_code)).limit(1))
        if not rows:
            # Fallback: if caller passed module_id separately, try to use that
            if fallback_module_id:
                return await ModuleRepository.assign_lecturer(fallback_module_id, lecturer_profile_id)
            return None
        module = rows[0]
        module_id = module.get("id")
        semester_id = module.get("semester_id")
        # Insert teaching_assignments row (idempotent due to unique constraint)
        ta_payload = {
            "semester_id": semester_id,
            "module_id": module_id,
            "lecturer_profile_id": int(lecturer_profile_id),
        }
        try:
            await _exec(client.table("teaching_assignments").insert(ta_payload))
        except Exception:
            # In case of unique violation or other DB errors, continue to update modules
            pass
        # Update modules.lecturer_id for compatibility
        try:
            await _exec(client.table("modules").update({"lecturer_id": lecturer_profile_id}).eq("id", module_id))
        except Exception:
            pass
        rows = await _exec(client.table("modules").select("*").eq("id", module_id).limit(1))
        return rows[0] if rows else None

    @staticmethod
    async def remove_lecturer_by_code(module_code: str) -> Optional[dict]:
        client = await get_supabase()
        rows = await _exec(client.table("modules").select("id").eq("code", str(module_code)).limit(1))
        if not rows:
            return None
        module_id = rows[0].get("id")
        # Delete teaching_assignments row(s) for this module
        try:
            await _exec(client.table("teaching_assignments").delete().eq("module_id", module_id))
        except Exception:
            pass
        # Clear modules.lecturer_id for compatibility
        try:
            await _exec(client.table("modules").update({"lecturer_id": None}).eq("id", module_id))
        except Exception:
            pass
        rows = await _exec(client.table("modules").select("*").eq("id", module_id).limit(1))
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

