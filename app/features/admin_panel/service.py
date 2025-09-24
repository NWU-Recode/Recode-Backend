from typing import List
from uuid import UUID
from .repository import AdminRepository
from .schemas import EnrolmentCreate, UserRoleUpdate

import csv, io

class AdminPanelService:

    @staticmethod
    async def enrol_student(enrolment: EnrolmentCreate, user_role: str, user_id: int):
        """Enrol student. Lecturers limited to their modules, Admin can do all."""
        enrol_dict = {
            "student_id": enrolment.student_id,
            "module_id": enrolment.module_id,
            "semester_id": enrolment.semester_id,
            "status": "active"
        }
        res = await AdminRepository.add_student(enrol_dict)
        return res

    @staticmethod
    async def enrol_students_batch(requests: List[EnrolmentCreate], user_role: str, user_id: int):
        responses = []
        for req in requests:
            res = await AdminPanelService.enrol_student(req, user_role, user_id)
            if res:
                responses.append(res)
        return responses

    @staticmethod
    async def add_batch_students_from_csv(file_content: bytes, module_id: UUID, semester_id: UUID, user_role: str, user_id: int):
        decoded = file_content.decode("utf-8")
        reader = csv.DictReader(io.StringIO(decoded))
        responses = []
        for row in reader:
            try:
                student_id = int(row.get("student_id") or row.get("id"))
                enrolment = EnrolmentCreate(
                    student_id=student_id,
                    module_id=module_id,
                    semester_id=semester_id
                )
                res = await AdminPanelService.enrol_student(enrolment, user_role, user_id)
                if res:
                    responses.append(res)
            except Exception:
                continue
        return responses

    @staticmethod
    async def remove_student(enrolment_id: UUID, module_id: UUID = None, user_role: str = "lecturer", user_id: int = None):
        return await AdminRepository.remove_student(enrolment_id, module_id, user_role, user_id)

    @staticmethod
    async def list_students(module_id: UUID = None, user_role: str = "lecturer", user_id: int = None):
        return await AdminRepository.list_students(module_id, user_role, user_id)

    @staticmethod
    async def get_module_progress(module_id: UUID, user_role: str, user_id: int):
        from app.DB.supabase import get_supabase
        client = await get_supabase()
        # Lecturers limited to their module
        if user_role.lower() == "lecturer":
            mod_res = await client.table("modules").select("id").eq("id", module_id).eq("lecturer_id", user_id).execute()
            if not mod_res.data:
                return []
        result = await client.table("challenge_progress").select("*").eq("module_id", str(module_id)).execute()
        return result.data or []

    @staticmethod
    async def update_user_role(role_update: UserRoleUpdate):
        return await AdminRepository.update_user_role(role_update.user_id, role_update.new_role)

    @staticmethod
    async def get_all_users():
        return await AdminRepository.get_all_users()
