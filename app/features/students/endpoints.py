# app/features/students/endpoints.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.DB.session import get_db
from app.common.deps import get_current_user_from_cookie, require_role
from app.features.profiles.models import Profile
from app.features.submissions.models import Submission
from app.features.badges.models import BadgeAward

router = APIRouter(prefix="/students", tags=["students"])

@router.get("/ping")
def students_ping():
    return {"ok": True, "who": "students"}

@router.get("/me")
async def student_me(current_user = Depends(get_current_user_from_cookie)):
    # return the current user claims so you can inspect fields
    return {"current_user": current_user}

@router.get("/me")
def get_my_profile(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_cookie),
):
    """
    Return the profile for the logged-in student (by email).
    get_current_user_from_cookie provides `email` and `role`.
    """
    profile = db.query(Profile).filter(Profile.email == current_user.email).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.get("/me/slides")
def get_my_slides(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_cookie),
):
    """
    Returns list of slides for all modules the student is enrolled in.
    Uses the Profile -> modules relationship added earlier.
    """
    profile = db.query(Profile).filter(Profile.email == current_user.email).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    slides_out = []
    for m in profile.modules:
        for s in getattr(m, "slides", []):
            slides_out.append({"module_id": m.id, "module_code": m.code, "slide_id": s.id, "title": s.title, "url": f"/uploads/slides/{s.filename}"})
    return slides_out


@router.get("/me/challenges")
def get_my_challenges(
    db: Session = Depends(get_db),
    current_user = Depends(require_role("student")),
):
    """
    Proxy to existing challenge service or endpoint.
    If you have a service function to retrieve challenges for a student, call it here.
    Example: return get_challenges_for_student(profile.id)
    """
    # A fallback approach that retrieves student challenges by first finding the user's profile via email, then fetching their challenges using a service function.
    return {"detail": "Use existing challenge endpoints/service - call them from here or consume existing /challenges endpoints."}


@router.get("/me/performance")
def get_my_performance(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_cookie),
):
    """
    Return average quiz/challenge score and badges for the student.
    """
    profile = db.query(Profile).filter(Profile.email == current_user.email).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    avg_score = db.query(func.avg(Submission.score)).filter(Submission.student_id == profile.id).scalar() or 0.0
    avg_score = float(round(avg_score, 2))

    badges = db.query(BadgeAward).filter(BadgeAward.profile_id == profile.id).all()
    # return simplified badge data
    badges_out = [{"id": b.id, "badge_id": getattr(b, "badge_id", None), "awarded_at": getattr(b, "awarded_at", None)} for b in badges]

    return {"avg_score": avg_score, "badges": badges_out}

@router.get("/me/profile")
def my_profile(db: Session = Depends(get_db), current_user = Depends(get_current_user_from_cookie)):
    # Adjust key: here we expect current_user.email to exist
    email = getattr(current_user, "email", None)
    if not email:
        raise HTTPException(status_code=400, detail="No email in auth claims")
    profile = db.query(Profile).filter(Profile.email == email).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile

@router.get("/challenges/{challenge_id}/stats")
def challenge_stats(challenge_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_from_cookie)):
    subs = db.query(Submission).filter(Submission.challenge_id == challenge_id).all()
    total_attempts = len(subs)
    unique_students = len({s.student_id for s in subs})
    avg_score = float(db.query(func.avg(Submission.score)).filter(Submission.challenge_id == challenge_id).scalar() or 0.0)
    # compute per-student avg & avg completion using started_at/submitted_at if present
    return {"challenge_id": challenge_id, "total_attempts": total_attempts, "unique_students": unique_students, "avg_score": round(avg_score,2)}

