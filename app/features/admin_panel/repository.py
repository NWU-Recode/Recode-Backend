from uuid import UUID
from typing import List
from app.DB.supabase import get_supabase
from .schemas import EnrolmentCreate

class AdminRepository:

    @staticmethod
    async def add_student(enrolment: EnrolmentCreate):
        supabase = await get_supabase()
        # Check if student already enrolled
        existing = await supabase.table("enrolments") \
            .select("*") \
            .eq("student_id", enrolment.student_id) \
            .eq("module_id", enrolment.module_id) \
            .eq("semester_id", enrolment.semester_id) \
            .execute()
        if existing.data:
            return None
        # Insert new enrolment
        result = await supabase.table("enrolments") \
            .insert(enrolment.dict()) \
            .execute()
        return result.data[0]

    @staticmethod
    async def add_students_batch(students: List[int], module_id: UUID, semester_id: UUID):
        supabase = await get_supabase()
        enrolments = [
            {"student_id": s, "module_id": module_id, "semester_id": semester_id, "status": "enrolled"}
            for s in students
        ]
        result = await supabase.table("enrolments").insert(enrolments).execute()
        return result.data

    @staticmethod
    async def list_students():
        supabase = await get_supabase()
        result = await supabase.table("enrolments").select("*").execute()
        return result.data
