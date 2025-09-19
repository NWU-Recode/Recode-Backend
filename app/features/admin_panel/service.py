from typing import List
from uuid import UUID
from .repository import AdminRepository
from .schemas import EnrolmentCreate
import csv, io
from app.features.challenges.repository import ChallengeRepository
from app.features.challenges.service import ChallengeService

class AdminPanelService:

    @staticmethod
    async def enrol_student(enrolment: EnrolmentCreate, lecturer_id: int):
        """Enrol a single student and initialize challenges"""
        enrol_dict = {
            "student_id": enrolment.student_id,
            "module_id": enrolment.module_id,
            "semester_id": enrolment.semester_id,
            "status": "active"
        }
        res = await AdminRepository.add_student(enrol_dict)
        if res:
            # Initialize challenges for the student
            #before
            #challenges = await ChallengeRepository.get_module_challenges(enrolment.module_id)
            #temporary fix
            challenges=[]
            for challenge in challenges:
                await ChallengeService.initialize_student_challenge(enrolment.student_id, challenge["id"])
        return res

    @staticmethod
    async def enrol_students_batch(requests: List[EnrolmentCreate], lecturer_id: int):
        responses = []
        for req in requests:
            res = await AdminPanelService.enrol_student(req, lecturer_id)
            if res:
                responses.append(res)
        return responses

    @staticmethod
    async def add_batch_students_from_csv(file_content: bytes, module_id: UUID, semester_id: UUID, lecturer_id: int):
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
                res = await AdminPanelService.enrol_student(enrolment, lecturer_id)
                if res:
                    responses.append(res)
            except Exception:
                continue
        return responses

    @staticmethod
    async def remove_student(enrolment_id: UUID, lecturer_id: int):
        return await AdminRepository.remove_student(enrolment_id, lecturer_id)

    @staticmethod
    async def list_students(lecturer_id: int):
        return await AdminRepository.list_students(lecturer_id)

    @staticmethod
    async def get_module_progress(module_id: UUID, lecturer_id: int):
        from app.DB.supabase import get_supabase
        client = await get_supabase()
        # Ensure the module belongs to this lecturer
        mod_res = await client.table("modules").select("id").eq("id", module_id).eq("lecturer_id", lecturer_id).execute()
        if not mod_res.data:
            return []
        result = await client.table("challenge_progress") \
            .select("*") \
            .eq("module_id", str(module_id)) \
            .execute()
        return result.data or []
