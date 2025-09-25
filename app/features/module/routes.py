from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
import os
import shutil

from app.DB.session import get_db
from app.common.deps import require_lecturer, require_role
from app.features.module.models import Module
from app.features.profiles.models import User
from app.DB.session import engine

router = APIRouter(prefix="/modules", tags=["Modules"])


# === Lecturer: Register student to module ===
@router.post("/{module_id}/register/{student_id}", dependencies=[Depends(require_lecturer)])
async def register_student_to_module(module_id: int, student_id: int, db: Session = Depends(get_db)):
    # Example placeholder logic — you should connect to your Student/Module DB tables
    module = db.query(Module).filter(Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")

    # For now just pretend we register a student here
    return {"message": f"Student {student_id} registered to module {module_id}"}

@router.post("/{module_id}/register/{student_id}", dependencies=[Depends(require_lecturer)])
async def register_student_to_module(module_id: int, student_id: int, db: Session = Depends(get_db)):
    module = db.query(Module).filter(Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")

    student = db.query(User).filter(User.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if student in module.students:
        return {"message": f"Student {student_id} is already registered to module {module_id}"}

    module.students.append(student)
    db.add(module)
    db.commit()
    db.refresh(module)

    return {"message": f"Student {student_id} registered to module {module_id}"}

# === Lecturer: List students in a module ===
@router.get("/{module_id}/students", dependencies=[Depends(require_lecturer)])
async def list_students_in_module(module_id: int, db: Session = Depends(get_db)):
    module = db.query(Module).filter(Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")

    students = [{"id": s.id, "name": s.name, "email": s.email} for s in module.students]

    return {"module_id": module_id, "students": students}