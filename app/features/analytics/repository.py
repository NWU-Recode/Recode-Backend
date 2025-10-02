from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from fastapi import HTTPException
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
def get_module_overview(db: Session, lecturer_id: Optional[int] = None):
    if lecturer_id is not None:
        query = text("""
            SELECT * FROM module_overview 
            WHERE lecturer_id = :lecturer_id
        """)
        result = db.execute(query, {"lecturer_id": lecturer_id})
    else:
        query = text("SELECT * FROM module_overview")  # admin: all modules
        result = db.execute(query)
    
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
    query = text("""
        SELECT gl.*
        FROM global_leaderboard gl
        JOIN profiles p ON p.id = gl.student_id
        WHERE p.role = 'student'
        ORDER BY gl.current_elo DESC
    """)
    result = db.execute(query)
    columns = result.keys()
    return [dict(zip(columns, row)) for row in result.fetchall()]

def get_challenge_progress_per_student(
    db: Session, 
    lecturer_id: int, 
    module_code: str,
    challenge_id: Optional[str] = None
):
    """
    Get student progress for challenges in a module.
    Shows: student info, challenge name, highest badge, total time spent.
    Time is calculated as sum of (finished_at - created_at) for all submissions.
    """
    #verifying lecturer owns module
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
            detail="Module not found or access denied"
        )
    
    #main query
    base_query = """
        WITH badge_hierarchy AS (
            SELECT 
                'bronze'::text as badge_type, 1 as priority
            UNION ALL SELECT 'silver'::text, 2
            UNION ALL SELECT 'gold'::text, 3
            UNION ALL SELECT 'ruby'::text, 4
            UNION ALL SELECT 'emerald'::text, 5
            UNION ALL SELECT 'diamond'::text, 6
        ),
        student_time_spent AS (
            SELECT 
                cs.user_id,
                cs.challenge_id,
                SUM(
                    EXTRACT(EPOCH FROM (cs.finished_at - cs.created_at)) * 1000
                ) as time_ms,
                COUNT(*) as submission_count
            FROM code_submissions cs
            WHERE cs.challenge_id IN (
                SELECT c.id FROM challenges c WHERE c.module_code = :module_code
                {challenge_filter}
            )
            AND cs.finished_at IS NOT NULL
            AND cs.created_at IS NOT NULL
            GROUP BY cs.user_id, cs.challenge_id
        ),
        student_badges AS (
            SELECT 
                ub.student_id,
                ub.challenge_id,
                b.badge_type::text as badge_type,
                bh.priority
            FROM user_badges ub
            JOIN badges b ON ub.badge_id = b.id
            JOIN badge_hierarchy bh ON b.badge_type::text = bh.badge_type
            WHERE ub.challenge_id IN (
                SELECT c.id FROM challenges c WHERE c.module_code = :module_code
                {challenge_filter}
            )
        )
        SELECT 
            p.id as student_number,
            p.full_name as student_name,
            c.id as challenge_id,
            c.title as challenge_name,
            COALESCE(
                (SELECT sb.badge_type 
                 FROM student_badges sb 
                 WHERE sb.student_id = e.student_id 
                   AND sb.challenge_id = c.id 
                 ORDER BY sb.priority DESC 
                 LIMIT 1),
                'none'
            ) as highest_badge,
            COALESCE(sts.time_ms, 0) as total_time_ms,
            COALESCE(sts.submission_count, 0) as total_submissions
        FROM enrolments e
        JOIN profiles p ON e.student_id = p.id
        CROSS JOIN challenges c
        LEFT JOIN student_time_spent sts ON sts.user_id = e.student_id 
            AND sts.challenge_id = c.id
        WHERE e.module_id = (SELECT id FROM modules WHERE code = :module_code)
          AND e.status = 'active'
          AND p.role = 'student'
          AND c.module_code = :module_code
          {challenge_filter}
        GROUP BY p.id, p.full_name, c.id, c.title, e.student_id, sts.time_ms, sts.submission_count
        ORDER BY p.full_name, c.title
    """
    
    #challenge filter
    if challenge_id:
        challenge_filter = "AND c.id = :challenge_id"
        query = text(base_query.format(challenge_filter=challenge_filter))
        result = db.execute(query, {
            "module_code": module_code,
            "challenge_id": challenge_id
        })
    else:
        challenge_filter = ""
        query = text(base_query.format(challenge_filter=challenge_filter))
        result = db.execute(query, {"module_code": module_code})
    
    columns = result.keys()
    return [dict(zip(columns, row)) for row in result.fetchall()]