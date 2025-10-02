from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import date, timedelta
from typing import Optional

def get_student_dashboard_from_db(student_id: int, db: Session):
    query = text("SELECT * FROM student_dashboard_1 WHERE student_id=:student_id")
    return db.execute(query, {"student_id": student_id}).first()

def get_current_week_number(db: Session) -> Optional[int]:
    #calculate current week number based on active semester.
    #get current active semester
    query = text("""
        SELECT 
            start_date,
            end_date
        FROM semesters
        WHERE is_current = true
        LIMIT 1
    """)
    
    result = db.execute(query)
    semester = result.fetchone()
    
    if not semester:
        return None
    
    start_date = semester[0]
    end_date = semester[1]
    
    # Ensure dates are date objects (not datetime)
    if hasattr(start_date, 'date'):
        start_date = start_date.date()
    if hasattr(end_date, 'date'):
        end_date = end_date.date()
    
    # Calculate week number
    today = date.today()
    
    if today < start_date:
        return 0  # Semester hasn't started yet
    elif today > end_date:
        # Semester ended - calculate total weeks
        days_diff = (end_date - start_date).days
        return (days_diff // 7) + 1
    else:
        # During semester - calculate current week
        days_diff = (today - start_date).days
        return (days_diff // 7) + 1