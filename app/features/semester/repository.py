from app.DB.supabase import get_supabase
from .schemas import SemesterCreate

class SemesterRepository:

    @staticmethod
    async def create_semester(semester: dict):
        supabase = await get_supabase()
        result = await supabase.table("semesters").insert(semester).execute()
        return result.data

    @staticmethod
    async def get_all_semesters():
        supabase = await get_supabase()
        result = await supabase.table("semesters").select("*").execute()
        return result.data

    @staticmethod
    async def get_current_semester():
        supabase = await get_supabase()
        result = await supabase.table("semesters").select("*").eq("is_current", True).execute()
        return result.data[0] if result.data else None
