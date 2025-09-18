from .repository import SemesterRepository
from .schemas import SemesterCreate

class SemesterService:

    @staticmethod
    async def create_semester(semester: SemesterCreate):
        return await SemesterRepository.create_semester(semester)

    @staticmethod
    async def list_semesters():
        return await SemesterRepository.get_all_semesters()

    @staticmethod
    async def current_semester():
        return await SemesterRepository.get_current_semester()
