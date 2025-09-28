from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from .service import *
from .schema import *
from app.common.deps import get_current_user, CurrentUser
from app.DB.session import get_db

router = APIRouter()

## ------------------- Student -------------------


@router.get("/student/challenges", response_model=List[StudentChallengeFeedbackOut])
def student_challenges(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Not authorized")
    return student_challenge_feedback_service(db, current_user.id)

# Badge Summary
@router.get("/badges", response_model=List[BadgeSummaryOut])
def badges(db: Session = Depends(get_db)):
    return badge_summary_service(db)

# Challenge Progress
@router.get("/challenges/progress", response_model=List[ChallengeProgressOut])
def challenge_progress(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "lecturer":
        raise HTTPException(status_code=403, detail="Lecturer access required")
    return challenge_progress_service(db, current_user.id, current_user.role)

# Question Progress
@router.get("/questions/progress", response_model=List[QuestionProgressOut])
def question_progress(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "lecturer":
        raise HTTPException(status_code=403, detail="Lecturer access required")
    return question_progress_service(db, current_user.id, current_user.role)

# Module Overview
@router.get("/modules/overview", response_model=List[ModuleOverviewOut])
def modules_overview(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "lecturer":
        raise HTTPException(status_code=403, detail="Lecturer access required")
    return module_overview_service(db, current_user.id, current_user.role)

# High-Risk Students
@router.get("/students/high-risk", response_model=List[HighRiskStudentOut])
def high_risk_students(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "lecturer":
        raise HTTPException(status_code=403, detail="Lecturer access required")
    return high_risk_students_service(db, current_user.id, current_user.role)

# Module Leaderboard
@router.get("/modules/leaderboard", response_model=List[ModuleLeaderboardOut])
def module_leaderboard(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["student", "lecturer"]:
        raise HTTPException(status_code=403, detail="Student or lecturer access required")
    return module_leaderboard_service(db, current_user.id, current_user.role)

# Global Leaderboard
@router.get("/global/leaderboard", response_model=List[GlobalLeaderboardOut])
def global_leaderboard(db: Session = Depends(get_db)):
    return global_leaderboard_service(db)
