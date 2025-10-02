from fastapi import APIRouter, Depends, HTTPException, Query
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
def badges(
    module_code: str = Query(..., description="Module code (e.g., CMPG323)"),
    challenge_id: Optional[str] = Query(None, description="Optional: Filter by specific challenge ID"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    return badge_summary_service(
        db, 
        current_user.id, 
        current_user.role, 
        module_code,
        challenge_id
    )
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
def lecturer_modules(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "lecturer":
        raise HTTPException(status_code=403, detail="Lecturer access required")
    return get_module_overview(db, lecturer_id=current_user.id)

@router.get("/admin/modules", response_model=List[AdminModuleOverviewOut])
def admin_modules(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return get_module_overview(db)  # no lecturer_id filter

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

@router.get(
    "/challenge-progress",
    response_model=List[ChallengeProgressResponse],
    summary="Get student progress per challenge (Lecturer only)",
    description=(
        "Get detailed student progress for challenges in a module.\n\n"
        "Returns for each student:\n"
        "- Student number and name\n"
        "- Challenge name\n"
        "- Highest badge earned (bronze → diamond, or none)\n"
        "- Total time spent (sum of execution times)\n"
        "- Total number of submissions\n\n"
        "Required: module_code\n"
        "Optional: challenge_id (filter to specific challenge)"
    )
)
def challenge_progress(
    module_code: str = Query(..., description="Module code (e.g., CMPG323)"),
    challenge_id: Optional[str] = Query(None, description="Optional: Filter by specific challenge UUID"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    
    return challenge_progress_service(
        db,
        current_user.id,
        current_user.role,
        module_code,
        challenge_id
    )