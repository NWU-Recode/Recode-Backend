from sqlalchemy.orm import Session
from sqlalchemy import text

# ------------------- Students -------------------



# Student Challenge Feedback
def get_student_challenges(db: Session, student_id: int):
    query = text("SELECT * FROM student_challenge_feedback WHERE student_id = :student_id")
    result = db.execute(query, {"student_id": student_id})
    columns = result.keys()
    return [dict(zip(columns, row)) for row in result.fetchall()]

# Badge Summary
def get_badge_summary(db: Session,lecturer_id: int):
    query = text("""SELECT *
        FROM badge_summary_module
        WHERE module_code IN (
            SELECT code
            FROM modules
            WHERE lecturer_id = :lecturer_id
        )
        ORDER BY module_code, badge_type;""")
    result = db.execute(query, {"lecturer_id": lecturer_id})
    columns = result.keys()
    return [dict(zip(columns, row)) for row in result.fetchall()]

# Challenge Progress Summary
def get_challenge_progress(db: Session,  lecturer_id: int):
    query = text(""" SELECT *
        FROM challenge_progress_summary cps
        JOIN modules m ON cps.module_code = m.code
        WHERE m.lecturer_id = :lecturer_id""")
    result = db.execute(query, {"lecturer_id": lecturer_id})
    columns = result.keys()
    return [dict(zip(columns, row)) for row in result.fetchall()]

# Question Progress Summary
def get_question_progress(db: Session, lecturer_id: int):
    query = text("""
        SELECT qps.* FROM question_progress_summary qps
        JOIN modules m ON qps.module_code = m.code
        WHERE m.lecturer_id = :lecturer_id
    """)
    result = db.execute(query, {"lecturer_id": lecturer_id})
    columns = result.keys()
    return [dict(zip(columns, row)) for row in result.fetchall()]

# Module Overview
def get_module_overview(db: Session, lecturer_id: int):
    query = text("""
        SELECT * FROM module_overview 
        WHERE lecturer_id = :lecturer_id
    """)
    result = db.execute(query, {"lecturer_id": lecturer_id})
    columns = result.keys()
    return [dict(zip(columns, row)) for row in result.fetchall()]

# Lecturer High-Risk Students
def get_high_risk_students(db: Session, lecturer_id: int):
    query = text("""
        SELECT hrs.* FROM lecturer_student_high_risk_snapshots hrs
        JOIN modules m ON hrs.module_code = m.code
        WHERE m.lecturer_id = :lecturer_id
    """)
    result = db.execute(query, {"lecturer_id": lecturer_id})
    columns = result.keys()
    return [dict(zip(columns, row)) for row in result.fetchall()]

# Module Leaderboard
def get_module_leaderboard(db: Session, user_id:int,role:str):
    if role == "lecturer":
        query = text("""
            SELECT ml.* FROM module_leaderboard ml
            JOIN modules m ON ml.module_id = m.id
            WHERE m.lecturer_id = :user_id
            ORDER BY ml.module_code, ml.rank_in_module
        """)
    else:  # student
        query = text("""
            SELECT ml.* FROM module_leaderboard ml
            JOIN enrolments e ON ml.module_id = e.module_id
            WHERE e.student_id = :user_id AND e.status = 'active'
            ORDER BY ml.module_code, ml.rank_in_module
        """)
    
    result = db.execute(query, {"user_id": user_id})
    columns = result.keys()
    return [dict(zip(columns, row)) for row in result.fetchall()]

# Global Leaderboard
def get_global_leaderboard(db: Session):
    query = text("SELECT * FROM global_leaderboard")
    result = db.execute(query)
    columns = result.keys()
    return [dict(zip(columns, row)) for row in result.fetchall()]
