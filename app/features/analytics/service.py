from __future__ import annotations
from typing import List, Dict, Any
from app.DB.supabase import get_supabase
from sqlalchemy.orm import Session
from .repository import *
from fastapi import HTTPException

#from .repository import *



def student_challenge_feedback_service(db: Session, student_id: int):
    return get_student_challenges(db, student_id)

# Badge Summary
def badge_summary_service(db: Session, user_id: int, role: str):
    if role != "lecturer":
        raise HTTPException(status_code=403, detail="Access denied")
    else:
        return get_badge_summary(db,user_id)

# Challenge Progress
def challenge_progress_service(db: Session,user_id: int, role: str):
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
        return get_module_overview(db, user_id)
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
