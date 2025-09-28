from app.DB.session import SessionLocal
from .models import Semester
from app.features.admin.models import Module


class SemesterRepository:

    @staticmethod
    def list_semesters():
        with SessionLocal() as db:
            return db.query(Semester).order_by(Semester.start_date).all()

    @staticmethod
    def create_semester(data):
        with SessionLocal() as db:
            new_sem = Semester(**data)
            db.add(new_sem)
            db.commit()
            db.refresh(new_sem)
            return new_sem

    @staticmethod
    def unset_current_semester():
        with SessionLocal() as db:
            db.query(Semester).filter(Semester.is_current == True).update({"is_current": False})
            db.commit()

    @staticmethod
    def get_current_semester():
        with SessionLocal() as db:
            return db.query(Semester).filter(Semester.is_current == True).first()
    @staticmethod
    def get_user_modules(semester_id: str, user_id: str):
        """
        Return all modules for a specific user and semester.
        """
        with SessionLocal() as db:
            return db.query(Module).filter(
                Module.semester_id == semester_id,
                Module.user_id == user_id
            ).all()