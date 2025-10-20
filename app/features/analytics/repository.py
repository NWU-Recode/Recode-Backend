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
def get_student_badges(
    db: Session,
    student_id: int,
    module_code: str,
    challenge_id: Optional[str] = None
):
    """
    Get badge summary for a specific student in a module using user_badge table.
    Joins through questions to get to challenges.
    """
    # Verify student is enrolled in the module
    verify_query = text("""
        SELECT e.id 
        FROM enrolments e
        JOIN modules m ON e.module_id = m.id
        WHERE m.code = :module_code 
          AND e.student_id = :student_id
          AND e.status = 'active'
    """)
    enrollment_check = db.execute(verify_query, {
        "module_code": module_code,
        "student_id": student_id
    }).fetchone()
    
    if not enrollment_check:
        raise HTTPException(
            status_code=403,
            detail="Not enrolled in this module or module not found"
        )
    
    if challenge_id:
        # Filter by specific challenge
        query = text("""
            SELECT 
                b.badge_type::text as badge_type,
                COUNT(ub.id) as badge_count,
                MAX(ub.date_earned)::text as latest_award
            FROM user_badge ub
            JOIN badges b ON ub.badge_id = b.id
            JOIN questions q ON ub.question_id = q.id
            WHERE q.challenge_id = :challenge_id::uuid
              AND ub.profile_id = :student_id
            GROUP BY b.badge_type
            ORDER BY b.badge_type
        """)
        result = db.execute(query, {
            "challenge_id": challenge_id,
            "student_id": student_id
        })
    else:
        # All badges for challenges in this module
        query = text("""
            SELECT 
                b.badge_type::text as badge_type,
                COUNT(ub.id) as badge_count,
                MAX(ub.date_earned)::text as latest_award
            FROM user_badge ub
            JOIN badges b ON ub.badge_id = b.id
            JOIN questions q ON ub.question_id = q.id
            JOIN challenges c ON q.challenge_id = c.id
            WHERE c.module_code = :module_code
              AND ub.profile_id = :student_id
            GROUP BY b.badge_type
            ORDER BY b.badge_type
        """)
        result = db.execute(query, {
            "module_code": module_code,
            "student_id": student_id
        })
    
    columns = result.keys()
    return [dict(zip(columns, row)) for row in result.fetchall()]


def get_badge_summary(
    db: Session, 
    lecturer_id: int, 
    module_code: str,
    challenge_id: Optional[str] = None
):
    """
    Get badge summary for a module owned by lecturer using user_badge table.
    Shows all students' badges aggregated.
    """
    # Verify lecturer owns this module
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
        # Filter by specific challenge
        query = text("""
            SELECT 
                b.badge_type::text as badge_type,
                COUNT(ub.id) as badge_count,
                MAX(ub.date_earned)::text as latest_award
            FROM user_badge ub
            JOIN badges b ON ub.badge_id = b.id
            JOIN questions q ON ub.question_id = q.id
            WHERE q.challenge_id = :challenge_id::uuid
            GROUP BY b.badge_type
            ORDER BY b.badge_type
        """)
        result = db.execute(query, {
            "challenge_id": challenge_id
        })
    else:
        # All badges for all challenges in this module
        query = text("""
            SELECT 
                b.badge_type::text as badge_type,
                COUNT(ub.id) as badge_count,
                MAX(ub.date_earned)::text as latest_award
            FROM user_badge ub
            JOIN badges b ON ub.badge_id = b.id
            JOIN questions q ON ub.question_id = q.id
            JOIN challenges c ON q.challenge_id = c.id
            WHERE c.module_code = :module_code
            GROUP BY b.badge_type
            ORDER BY b.badge_type
        """)
        result = db.execute(query, {"module_code": module_code})
    
    columns = result.keys()
    return [dict(zip(columns, row)) for row in result.fetchall()]

# Challenge Progress Summary
def get_challenge_progress(db: Session,  lecturer_id: int):
    query = text("""  SELECT 
            cps.challenge_id,
            cps.challenge_name,
            cps.challenge_type,
            cps.week_number,
            cps.challenge_tier,
            cps.module_code,
            cps.total_enrolled_students,
            cps.students_completed,
            cps.total_question_attempts,
            cps.challenge_participation_rate,
            cps.challenge_completion_rate,
            cps.difficulty_breakdown,
            cps.avg_elo_of_successful_students,
            cps.avg_completion_time_minutes,
            cps.challenge_status
        FROM challenge_progress_summary cps
        JOIN modules m ON cps.module_code = m.code
        WHERE m.lecturer_id = :lecturer_id
    """)
    result = db.execute(query, {"lecturer_id": lecturer_id})
    columns = result.keys()
    return [dict(zip(columns, row)) for row in result.fetchall()]

# Question Progress Summary
def get_question_progress(db: Session, lecturer_id: int):
    query = text("""
        SELECT 
            qps.question_number,
            qps.question_type,
            qps.challenge_name,
            qps.challenge_tier,
            qps.module_code,
            qps.students_attempted,
            qps.total_submissions,
            qps.correct_submissions,
            qps.success_rate,
            qps.avg_elo_earned,
            qps.avg_completion_time_minutes
        FROM question_progress_summary qps
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
        query = text("""
        SELECT 
            m.id,
            m.code,
            m.name,
            m.description,
            m.semester_id,
            m.lecturer_id,
            m.code_language,
            m.credits
        FROM modules m
        ORDER BY m.code
    """)  # admin: all modules
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
        SELECT
            gl.student_id,
            gl.full_name,
            gl.current_elo,
            gl.total_badges,
            gl.global_rank,
            t.name AS title_name
        FROM global_leaderboard gl
        JOIN profiles p ON p.id = gl.student_id
        LEFT JOIN titles t ON t.id = p.title_id
        ORDER BY gl.current_elo DESC
    """)
    result = db.execute(query)
    columns = result.keys()
    return [dict(zip(columns, row)) for row in result.fetchall()]



def get_challenge_progress_per_student(
    db: Session, 
    lecturer_id: int, 
    module_code: str,
):
    """
    Get student progress for challenges in a module.
    Shows: student info, challenge name, highest badge, total time spent, total submissions.
    """
    # Verify lecturer owns module
    module_check = db.execute(
        text("SELECT code FROM modules WHERE code = :module_code AND lecturer_id = :lecturer_id"),
        {"module_code": module_code, "lecturer_id": lecturer_id}
    ).fetchone()
    
    if not module_check:
        raise HTTPException(status_code=403, detail="Module not found or access denied")
    # Main query
    query = f"""
        WITH badge_hierarchy AS (
            SELECT 'bronze' AS badge_type, 1 AS priority
            UNION ALL SELECT 'silver', 2
            UNION ALL SELECT 'gold', 3
            UNION ALL SELECT 'ruby', 4
            UNION ALL SELECT 'emerald', 5
            UNION ALL SELECT 'diamond', 6
        ),
        student_time_spent AS (
            SELECT 
                cs.user_id,
                q.challenge_id,
                SUM(EXTRACT(EPOCH FROM (cs.finished_at - cs.created_at)) * 1000) AS time_ms,
                COUNT(*) AS submission_count
            FROM code_submissions cs
            JOIN questions q ON cs.question_id = q.id
            WHERE cs.finished_at IS NOT NULL AND cs.created_at IS NOT NULL
            GROUP BY cs.user_id, q.challenge_id
        ),
        student_badges AS (
            SELECT
                ub.profile_id AS student_id,
                q.challenge_id,
                b.badge_type::text AS badge_type,
                bh.priority
            FROM user_badge ub
            JOIN badges b ON ub.badge_id = b.id
            JOIN questions q ON ub.question_id = q.id
            JOIN badge_hierarchy bh ON b.badge_type::text = bh.badge_type
        )
        SELECT
            p.id AS student_number,
            p.full_name AS student_name,
            c.id AS challenge_id,
            c.title AS challenge_name,
            COALESCE(
                (SELECT sb.badge_type
                 FROM student_badges sb
                 WHERE sb.student_id = e.student_id AND sb.challenge_id = c.id
                 ORDER BY sb.priority DESC LIMIT 1),
                'none'
            ) AS highest_badge,
            COALESCE(sts.time_ms, 0) AS total_time_ms,
            COALESCE(sts.submission_count, 0) AS total_submissions
        FROM enrolments e
        JOIN profiles p ON e.student_id = p.id
        JOIN challenges c ON c.module_code = :module_code 
        LEFT JOIN student_time_spent sts ON sts.user_id = e.student_id AND sts.challenge_id = c.id
        WHERE e.module_id = (SELECT id FROM modules WHERE code = :module_code)
          AND e.status = 'active'
          AND p.role = 'student'
        ORDER BY p.full_name, c.title
    """

    params = {"module_code": module_code}

    result = db.execute(text(query), params)
    columns = result.keys()
    return [dict(zip(columns, row)) for row in result.fetchall()]
