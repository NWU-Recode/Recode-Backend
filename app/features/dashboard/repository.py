from sqlalchemy.orm import Session
from sqlalchemy import text

def get_student_dashboard_from_db(student_id: int, db: Session):
    query = text("SELECT * FROM student_dashboard_1 WHERE student_id=:student_id")
    return db.execute(query, {"student_id": student_id}).first()