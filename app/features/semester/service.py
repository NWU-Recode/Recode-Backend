from typing import List
from app.DB.session import SessionLocal  
from .repository import SemesterRepository
from .schemas import ModuleResponse, SemesterCreate, SemesterResponse
from app.features.admin.models import Module  

class SemesterService:

    @staticmethod
    def create_semester(semester: SemesterCreate) -> SemesterResponse:
        data = semester.model_dump()
        data['term_name'] = data['term_name'].capitalize()  # normalize input

        if data.get("is_current"):
            SemesterRepository.unset_current_semester()  # synchronous

        try:
            created = SemesterRepository.create_semester(data)
        except Exception as e:
            if "semesters_term_name_check" in str(e):
                raise ValueError("Invalid term_name")
            raise

        return SemesterResponse.model_validate(created)

    @staticmethod
    def list_semesters() -> List[SemesterResponse]:
        semesters = SemesterRepository.list_semesters()
        return [SemesterResponse.model_validate(s) for s in semesters]

    @staticmethod
    def current_semester() -> SemesterResponse:
        current = SemesterRepository.get_current_semester()
        if not current:
            raise ValueError("No current semester found")
        return SemesterResponse.model_validate(current)
    
    @staticmethod
    def get_user_modules(semester_id: str, user_id: str) -> List[ModuleResponse]:
        with SessionLocal() as db:
            modules = db.query(Module).filter(Module.semester_id == semester_id).all()
            return [ModuleResponse.model_validate(m) for m in modules]
