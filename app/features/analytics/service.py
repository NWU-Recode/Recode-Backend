from __future__ import annotations
from typing import List, Dict, Any, Optional
from app.DB.supabase import get_supabase
from sqlalchemy.orm import Session
from .repository import *
from .schema import *
from fastapi import HTTPException

#from .repository import *



def student_challenge_feedback_service(db: Session, student_id: int):
    return get_student_challenges(db, student_id)

# Badge Summary
def badge_summary_service(
    db: Session, 
    user_id: int, 
    role: str, 
    module_code: str,
    challenge_id: Optional[str] = None
):
    """Get badge summary - lecturers see all, students see their own."""
    if role == "lecturer":
        return get_badge_summary(db, user_id, module_code, challenge_id)
    elif role == "student":
        return get_student_badges(db, user_id, module_code, challenge_id)
    else:
        raise HTTPException(
            status_code=403, 
            detail="Access denied. Must be student or lecturer."
        )

def challenge_progress_services(db: Session,user_id: int, role: str):
    if role == "lecturer":
        return get_challenge_progress(db, user_id)
    else:
        raise HTTPException(status_code=403, detail="Access denied")

# Question Progress
def question_progress_service(db: Session, user_id: int, role: str):
    if role == "lecturer":
        return get_question_progress(db, user_id)
    else:
        raise HTTPException(status_code=403, detail="Access denied")

# Module Overview
def module_overview_service(db: Session, user_id: int, role: str):
    if role == "lecturer":
        return get_module_overview(db, lecturer_id=user_id)
    elif role == "admin":
        return get_module_overview(db) 
    else:
        raise HTTPException(status_code=403, detail="Access denied")

# High-Risk Students
def high_risk_students_service(db: Session, user_id: int, role: str):
    if role == "lecturer":
        return get_high_risk_students(db, user_id)
    else:
        raise HTTPException(status_code=403, detail="Access denied")

# Module Leaderboard
def module_leaderboard_service(db: Session, user_id: int, role: str):
    return get_module_leaderboard(db, user_id, role)

# Global Leaderboard
def global_leaderboard_service(db: Session):
    return get_global_leaderboard(db)

def challenge_progress_service(
    db: Session,
    user_id: int,
    role: str,
    module_code: str,

):
    if role != "lecturer":
        raise HTTPException(status_code=403, detail="Access denied. Lecturer role required.")
    
    return get_challenge_progress_per_student(db, user_id, module_code)

def get_student_elo_weekly(
    student_id: int,
    module_code: Optional[str] = None,
) -> List[StudentEloDistributionWeekly]:
    """Get weekly ELO distribution for a student."""
    data =get_student_elo_distribution_weekly(
        student_id=student_id,
        module_code=module_code,
    )
    return [StudentEloDistributionWeekly(**record) for record in data]

