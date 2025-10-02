from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
# ------------------- Students -------------------



# Student Challenge Feedback
def get_student_challenges(db: Session, student_id: int):
    query = text("SELECT * FROM student_challenge_feedback WHERE student_id = :student_id")
    result = db.execute(query, {"student_id": student_id})
    columns = result.keys()
    return [dict(zip(columns, row)) for row in result.fetchall()]

# Badge Summary
def get_badge_summary(
    db: Session, 
    lecturer_id: int, 
    module_code: str,
    challenge_id: Optional[str] = None
):
    """
    Get badge summary for a specific module owned by lecturer.
    If challenge_id provided, filter to that specific challenge.
    """
    # First verify lecturer owns this module
    verify_query = text("""
        SELECT code FROM modules 
        WHERE code = :module_code AND lecturer_id = :lecturer_id
    """)
    module_check = db.execute(verify_query, {
        "module_code": module_code, 
        "lecturer_id": lecturer_id
    }).fetchone()
    
    if not module_check:
        raise HTTPException(
            status_code=403, 
            detail="Module not found or you don't have access"
        )
    
    if challenge_id:
        # Filter by specific challenge within the module
        query = text("""
            SELECT 
                b.badge_type,
                COUNT(*) as badge_count,
                MAX(ub.awarded_at)::text as latest_award
            FROM user_badges ub
            JOIN badges b ON ub.badge_id = b.id
            JOIN challenges c ON ub.challenge_id = c.id
            WHERE c.module_code = :module_code
              AND c.id = :challenge_id
            GROUP BY b.badge_type
            ORDER BY b.badge_type
        """)
        result = db.execute(query, {
            "module_code": module_code,
            "challenge_id": challenge_id
        })
    else:
        # All badges for the entire module
        query = text("""
            SELECT 
                b.badge_type,
                COUNT(*) as badge_count,
                MAX(ub.awarded_at)::text as latest_award
            FROM user_badges ub
            JOIN badges b ON ub.badge_id = b.id
            JOIN challenges c ON ub.challenge_id = c.id
            WHERE c.module_code = :module_code
            GROUP BY b.badge_type
            ORDER BY b.badge_type
        """)
        result = db.execute(query, {"module_code": module_code})
    
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
    query = text("""SELECT * FROM global_leaderboard WHERE role = 'student' ORDER BY current_elo DESC""")
    result = db.execute(query)
    columns = result.keys()
    return [dict(zip(columns, row)) for row in result.fetchall()]
