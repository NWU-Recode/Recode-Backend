from typing import List, Optional
from uuid import UUID

from app.common.deps import CurrentUser

from .schemas import (
    ModuleCreate, ModuleResponse,
    ChallengeCreate, ChallengeResponse,
    StudentResponse,
)
from .repository import ModuleRepository, LecturerRepository


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
    async def delete_module(module_id: UUID) -> bool:
        return await ModuleRepository.delete_module(module_id)

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

        result = []
        for s in students:
            if not s or "student_number" not in s or s["student_number"] is None:
                continue
            result.append(StudentResponse(student_number=int(s["student_number"])))
        return result if result else None
    
    @staticmethod
    async def add_challenge(module_code: str, challenge: ChallengeCreate, lecturer_id: int) -> Optional[ChallengeResponse]:
        data = await ModuleRepository.add_challenge(module_code, challenge, lecturer_id)
        return ChallengeResponse(**data) if data else None

    @staticmethod
    async def get_challenges(module_code: str, user: CurrentUser) -> Optional[List[ChallengeResponse]]:
        """Get challenges with conditional fields based on challenge_type."""
        if user.role.lower() == "student":
            enrolled = await ModuleRepository.is_enrolled_by_code(module_code, user.id)
            if not enrolled:
                return None
        elif user.role.lower() == "lecturer":
            module = await ModuleRepository.get_module_by_code(module_code)
            if not module or module["lecturer_id"] != user.id:
                return None
        
        challenges = await ModuleRepository.get_challenges(module_code)
        
        # Transform to response objects
        result = []
        for c in challenges:
            # Create response with all fields
            challenge_data = {
                "id": c.get("id"),
                "module_code": c.get("module_code"),
                "challenge_type": c.get("challenge_type"),
                "title": c.get("title"),
                "description": c.get("description"),
                "status": c.get("status"),
                "release_date": c.get("release_date"),
                "due_date": c.get("due_date"),
                "created_at": c.get("created_at"),
                "updated_at": c.get("updated_at"),
            }
            
            # Add conditional fields based on challenge_type
            if c.get("challenge_type") == "weekly":
                challenge_data["week_number"] = c.get("week_number")
            elif c.get("challenge_type") == "special":
                challenge_data["tier"] = c.get("tier")
                challenge_data["trigger_event"] = c.get("trigger_event")
            
            result.append(ChallengeResponse(**challenge_data))
        
        return result


    @staticmethod
    async def enrol_student(module_code: str, student_number: int, lecturer_id: int, semester_id: Optional[UUID] = None) -> Optional[dict]:
        # Ensure the lecturer owns the module
        module = await ModuleRepository.get_module(module_code)
        if not module or module.get("lecturer_id") != lecturer_id:
            return None
        module_id = module["id"]
        return await ModuleRepository.add_enrolment(module_id, student_number, semester_id)

    @staticmethod
    async def enrol_students_batch(module_code: str, student_ids: List[int], lecturer_id: int, semester_id: Optional[UUID] = None) -> List[dict]:
        module = await ModuleRepository.get_module(module_code)
        if not module or module.get("lecturer_id") != lecturer_id:
            return {"created": [], "skipped": [], "failed": []}
        module_id = module["id"]
        return await ModuleRepository.add_enrolments_batch(module_id, student_ids, semester_id)

    @staticmethod
    async def assign_lecturer(module_id: UUID, lecturer_profile_id: int) -> Optional[dict]:
        return await ModuleRepository.assign_lecturer(module_id, lecturer_profile_id)

    @staticmethod
    async def remove_lecturer(module_id: UUID) -> Optional[dict]:
        return await ModuleRepository.remove_lecturer(module_id)

    #@staticmethod
    #async def create_semester(year: int, term_name: str, start_date, end_date, is_current: bool = False) -> Optional[dict]:
      #  return await ModuleRepository.create_semester(year, term_name, start_date, end_date, is_current)

    @staticmethod
    async def get_current_semester() -> Optional[dict]:
        return await ModuleRepository.get_current_semester()

    # --- Module-code helpers (moved from module.service) -----------------
    @staticmethod
    async def assign_lecturer_by_code(module_code: str, lecturer_profile_id: int, fallback_module_id: Optional[UUID] = None) -> Optional[dict]:
        return await ModuleRepository.assign_lecturer_by_code(module_code, lecturer_profile_id, fallback_module_id)

    @staticmethod
    async def remove_lecturer_by_code(module_code: str) -> Optional[dict]:
        return await ModuleRepository.remove_lecturer_by_code(module_code)

    @staticmethod
    async def get_semester_start_for_module_code(module_code: str):
        """Return a date or None: prefer the semester.start_date for the module identified by module_code,
        otherwise fall back to the current semester start."""
        mod = await ModuleRepository.get_module_by_code(module_code)
        if mod and mod.get("semester_id"):
            sem = await ModuleRepository.get_semester_by_id(mod.get("semester_id"))
            if sem and sem.get("start_date"):
                sd = sem.get("start_date")
                # ensure it's a date object or ISO string
                if isinstance(sd, str):
                    try:
                        from datetime import date
                        return date.fromisoformat(sd)
                    except Exception:
                        return None
                return sd
        # fallback
        curr = await ModuleRepository.get_current_semester()
        if curr and curr.get("start_date"):
            sd = curr.get("start_date")
            if isinstance(sd, str):
                try:
                    from datetime import date
                    return date.fromisoformat(sd)
                except Exception:
                    return None
            return sd
        return None

    @staticmethod
    async def admin_create_module(payload, admin_user_id: int) -> Optional[ModuleResponse]:
        # payload is expected to be ModuleAdminCreate-like or ModuleCreate
        # Ensure code normalized
        module = ModuleCreate(
            code=payload.code,
            name=payload.name,
            description=payload.description,
            semester_id=payload.semester_id,
            lecturer_id=payload.lecturer_id,
            code_language=getattr(payload, 'code_language', None),
            credits=getattr(payload, 'credits', None),
        )
        created = await ModuleRepository.create_module(module, payload.lecturer_id)
        return ModuleResponse(**created) if created else None

    # --- Helpers that operate on module_code (used by endpoints) -----------------
    

    
    @staticmethod
    async def update_module_by_code(module_code: str, module: ModuleCreate, admin_user_id: int) -> Optional[ModuleResponse]:
        mod = await ModuleRepository.get_module_by_code(module_code)
        if not mod:
            return None
        return await ModuleService.update_module(mod.get("id"), module, admin_user_id)
    
    @staticmethod
    async def delete_module_by_code(module_code: str, admin_user_id: int) -> bool:
        mod = await ModuleRepository.get_module_by_code(module_code)
        if not mod:
            return False
        return await ModuleService.delete_module(mod.get("id"), admin_user_id)

    @staticmethod
    async def get_students_by_code(module_code: str, lecturer_id: int):
        mod = await ModuleRepository.get_module_by_code(module_code)
        if not mod:
            return None
        return await ModuleService.get_students(mod.get("id"), lecturer_id)

    @staticmethod
    async def get_challenges_by_code(module_code: str, user: CurrentUser):
        return await ModuleService.get_challenges(module_code, user)

    @staticmethod
    async def enrol_student_by_code(module_code: str, student_number: int, lecturer_id: int, semester_id: Optional[UUID] = None):
        mod = await ModuleRepository.get_module_by_code(module_code)
        if not mod:
            return None
        return await ModuleService.enrol_student(mod.get("id"), student_number, lecturer_id, semester_id)

    @staticmethod
    async def enrol_students_batch_by_code(module_code: str, student_numbers: list[int], lecturer_id: int, semester_id: Optional[UUID] = None):
        mod = await ModuleRepository.get_module_by_code(module_code)
        if not mod:
            return None
        return await ModuleService.enrol_students_batch(mod.get("id"), student_numbers, lecturer_id, semester_id)

    @staticmethod
    async def enrol_students_csv_by_code(module_code: str, csv_bytes: bytes, lecturer_id: int):
        mod = await ModuleRepository.get_module_by_code(module_code)
        if not mod:
            return {"error": "module_not_found"}
        return await ModuleService.enrol_students_csv(mod.get("id"), csv_bytes, lecturer_id)

    @staticmethod
    async def enrol_students_csv(module_id: UUID, csv_bytes: bytes, lecturer_id: int, semester_id: Optional[UUID] = None) -> dict:
        """
        Parse CSV content. Expected columns: either 'student_id' or 'email'.
        Process rows idempotently (skip existing enrolments).
        Return summary: created/skipped/failed with details.
        """
        import csv
        from io import StringIO

        module = await ModuleRepository.get_module(module_id)
        if not module or module.get("lecturer_id") != lecturer_id:
            return {"error": "not_authorized_or_module_not_found"}

        text = csv_bytes.decode("utf-8")
        reader = csv.DictReader(StringIO(text))
        results = {"created": [], "skipped": [], "failed": []}

        async def resolve_and_insert(row):
            # Try to find student id by 'student_id' or 'email'
            sid = None
            if 'student_id' in row and row['student_id'].strip():
                try:
                    sid = int(row['student_id'])
                except Exception:
                    sid = None
            if sid is None and 'email' in row and row['email'].strip():
                prof = await ModuleRepository.get_profile_by_email(row['email'].strip())
                if prof:
                    sid = prof.get('id')
            if sid is None:
                return (False, {'row': row, 'reason': 'could_not_resolve_student'})

            res = await ModuleRepository.add_enrolment_if_not_exists(module_id, sid, semester_id)
            if res.get('created'):
                return (True, res)
            else:
                return (None, res)

        # sequentially process rows to avoid hammering DB; could be parallelized later
        async for r in _async_csv_iter(reader):
            ok, info = await resolve_and_insert(r)
            if ok is True:
                results['created'].append(info)
            elif ok is None:
                results['skipped'].append(info)
            else:
                results['failed'].append(info)

        return results


async def _async_csv_iter(reader):
    # Helper to iterate csv.DictReader in async contexts
    for row in reader:
        yield row

class LecturerService:
    @staticmethod
    async def get_lecturer_profile(lecturer_id: str) -> Optional[dict]:
        return await LecturerRepository.get_lecturer_by_id(lecturer_id)

