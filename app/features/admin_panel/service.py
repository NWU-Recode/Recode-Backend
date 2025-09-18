# admin_panel/service.py
from .repository import AdminRepository
from .schemas import EnrolmentCreate, EnrolmentBatch
from uuid import UUID
from typing import List
import csv
import io
from app.features.challenges.repository import ChallengeRepository
from app.features.challenges.service import ChallengeService

class AdminService:

    @staticmethod
    async def add_student(enrolment: EnrolmentCreate):
        # Add single student and return enrolment
        res = await AdminRepository.add_student(enrolment)
        if res:
            # Initialize challenges for this student
            challenges = await ChallengeRepository.get_module_challenges(enrolment.module_id)
            for challenge in challenges:
                await ChallengeService.initialize_student_challenge(enrolment.student_id, challenge["id"])
        return res

    @staticmethod
    async def add_students_batch(batch: EnrolmentBatch):
        responses = []
        for student_id in batch.students:
            enrolment = EnrolmentCreate(
                student_id=student_id,
                module_id=batch.module_id,
                semester_id=batch.semester_id
            )
            res = await AdminService.add_student(enrolment)
            if res:
                responses.append(res)
        return responses

    @staticmethod
    async def add_batch_students_from_csv(file_content: bytes, module_id: UUID, semester_id: UUID):
        decoded = file_content.decode('utf-8')
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
                res = await AdminService.add_student(enrolment)
                if res:
                    responses.append(res)
            except Exception:
                # skip invalid rows
                continue
        return responses

    @staticmethod
    async def list_students():
        return await AdminRepository.list_students()
