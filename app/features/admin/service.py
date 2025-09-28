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

    @staticmethod
    async def enrol_student(module_id: UUID, student_id: int, lecturer_id: int, semester_id: Optional[UUID] = None) -> Optional[dict]:
        # Ensure the lecturer owns the module
        module = await ModuleRepository.get_module(module_id)
        if not module or module.get("lecturer_id") != lecturer_id:
            return None
        return await ModuleRepository.add_enrolment(module_id, student_id, semester_id)

    @staticmethod
    async def enrol_students_batch(module_id: UUID, student_ids: List[int], lecturer_id: int, semester_id: Optional[UUID] = None) -> List[dict]:
        module = await ModuleRepository.get_module(module_id)
        if not module or module.get("lecturer_id") != lecturer_id:
            return {"created": [], "skipped": [], "failed": []}
        return await ModuleRepository.add_enrolments_batch(module_id, student_ids, semester_id)

    @staticmethod
    async def assign_lecturer(module_id: UUID, lecturer_profile_id: int) -> Optional[dict]:
        return await ModuleRepository.assign_lecturer(module_id, lecturer_profile_id)

    @staticmethod
    async def remove_lecturer(module_id: UUID) -> Optional[dict]:
        return await ModuleRepository.remove_lecturer(module_id)

    @staticmethod
    async def create_semester(year: int, term_name: str, start_date, end_date, is_current: bool = False) -> Optional[dict]:
        return await ModuleRepository.create_semester(year, term_name, start_date, end_date, is_current)

    @staticmethod
    async def get_current_semester() -> Optional[dict]:
        return await ModuleRepository.get_current_semester()

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
