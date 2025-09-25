# app/features/lecturers/endpoints.py
from fastapi import APIRouter, Depends, Body, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.DB.session import get_db
from app.common.deps import get_current_user_from_cookie, require_role
from app.features.profiles.models import Profile
from app.features.module.models import Module
from app.features.submissions.models import Submission
from app.features.badges.models import BadgeAward

# If your challenge service provides update/edit functions, import them
# from app.features.challenges.service import update_challenge

router = APIRouter(prefix="/lecturers", tags=["lecturers"])

@router.get("/ping")
def lecturers_ping():
    return {"ok": True, "who": "lecturers"}

@router.get("/me")
async def lecturer_me(current_user = Depends(get_current_user_from_cookie)):
    return {"current_user": current_user}

@router.get("/me")
def get_my_profile(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_cookie),
):
    profile = db.query(Profile).filter(Profile.email == current_user.email).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    if profile.role != "lecturer":
        raise HTTPException(status_code=403, detail="Not a lecturer")
    return profile


@router.get("/challenges/{challenge_id}/stats", dependencies=[Depends(require_role("lecturer"))])
def challenge_stats(challenge_id: int, db: Session = Depends(get_db)):
    """
    Compute stats for a challenge: total attempts, unique students, avg score,
    per-student average score and avg completion time.
    """
    subs = db.query(Submission).filter(Submission.challenge_id == challenge_id).all()
    total_attempts = len(subs)
    unique_students = len({s.student_id for s in subs})
    avg_score = float(db.query(func.avg(Submission.score)).filter(Submission.challenge_id == challenge_id).scalar() or 0.0)

    # per-student aggregation
    per_student = {}
    durations = []
    for s in subs:
        pid = s.student_id
        st = per_student.setdefault(pid, {"attempts": 0, "total_score": 0.0, "durations": []})
        st["attempts"] += 1
        st["total_score"] += (s.score or 0)
        if s.started_at and s.submitted_at:
            dur = (s.submitted_at - s.started_at).total_seconds()
            st["durations"].append(dur)
            durations.append(dur)

    per_student_out = []
    for pid, v in per_student.items():
        avg_score_st = float(v["total_score"] / v["attempts"]) if v["attempts"] else 0.0
        avg_dur = float(sum(v["durations"]) / len(v["durations"])) if v["durations"] else None
        per_student_out.append({"student_id": pid, "attempts": v["attempts"], "avg_score": round(avg_score_st, 2), "avg_completion_seconds": avg_dur})

    avg_completion_seconds = float(sum(durations) / len(durations)) if durations else None

    # badges for this challenge (if any)
    badges = db.query(BadgeAward).filter(BadgeAward.challenge_id == challenge_id).all() if hasattr(BadgeAward, "challenge_id") else []
    badges_out = [{"id": b.id, "badge_id": getattr(b, "badge_id", None)} for b in badges]

    return {
        "challenge_id": challenge_id,
        "total_attempts": total_attempts,
        "unique_students": unique_students,
        "avg_score": round(avg_score, 2),
        "avg_completion_seconds": avg_completion_seconds,
        "badges": badges_out,
        "per_student": per_student_out,
    }


@router.get("/modules/{module_id}/students", dependencies=[Depends(require_role("lecturer"))])
def list_module_students(module_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_from_cookie)):
    module = db.query(Module).filter(Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    # ensure current lecturer owns the module (owner_id)
    profile = db.query(Profile).filter(Profile.email == current_user.email).first()
    if module.owner_id != profile.id and profile.role != "admin":
        raise HTTPException(status_code=403, detail="Only module owner may view students")
    students = [{"id": s.id, "display_name": s.display_name, "email": s.email} for s in module.students]
    return students


@router.post("/modules/{module_id}/students", dependencies=[Depends(require_role("lecturer"))])
def register_student_to_module(module_id: int, student_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_from_cookie)):
    module = db.query(Module).filter(Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")

    profile = db.query(Profile).filter(Profile.email == current_user.email).first()
    if module.owner_id != profile.id and profile.role != "admin":
        raise HTTPException(status_code=403, detail="Only module owner may register students")

    student = db.query(Profile).filter(Profile.id == student_id, Profile.role == "student").first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if student in module.students:
        return {"message": "Student already registered"}

    module.students.append(student)
    db.add(module)
    db.commit()
    return {"message": "Student registered", "student_id": student_id, "module_id": module_id}

@router.get("/modules/{module_id}/students")
def list_module_students(module_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_from_cookie)):
    module = db.query(Module).filter(Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    # simple owner check: module.owner_id should match current profile.id
    profile = db.query(Profile).filter(Profile.email == getattr(current_user, "email", None)).first()
    if module.owner_id != profile.id and profile.role != "admin":
        raise HTTPException(status_code=403, detail="Only owner or admin")

    return [{"id": s.id, "email": s.email, "display_name": s.display_name} for s in module.students]

@router.post("/modules/{module_id}/students")
def register_student(module_id: int, student_id: int = Body(..., embed=True), db: Session = Depends(get_db), current_user = Depends(get_current_user_from_cookie)):
    module = db.query(Module).filter(Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    profile = db.query(Profile).filter(Profile.email == getattr(current_user, "email", None)).first()
    if module.owner_id != profile.id and profile.role != "admin":
        raise HTTPException(status_code=403, detail="Only owner or admin")
    student = db.query(Profile).filter(Profile.id == student_id, Profile.role == "student").first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    if student in module.students:
        return {"message": "already registered"}
    module.students.append(student)
    db.add(module)
    db.commit()
    return {"message": "registered", "module_id": module_id, "student_id": student_id}