from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Optional
from io import StringIO
import csv

from .service import lecturer_service
from .schemas import StudentProgressResponse, ExerciseResponse, ModuleModel, AnalyticsResponse

router = APIRouter(prefix="/lecturer", tags=["lecturer"])


# STUDENT PROGRESS

@router.get("/students", response_model=List[StudentProgressResponse])
async def list_students():
    """List all students with progress"""
    return await lecturer_service.list_students_with_progress()

@router.get("/students/export.csv")
async def export_students_csv():
    """Export students' progress as CSV"""
    rows = await lecturer_service.list_students_with_progress()
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["student_id", "email", "plain_pct", "ruby", "emerald", "diamond", "blended_pct"])
    for r in rows:
        writer.writerow([
            r.id,
            r.email,
            r.plain_pct,
            int(r.ruby_correct),
            int(r.emerald_correct),
            int(r.diamond_correct),
            r.blended_pct,
        ])
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=students_progress.csv"})


# SLIDES UPLOAD & EXERCISE GENERATION

@router.post("/slides/upload")
async def upload_slides(file: UploadFile = File(...)):
    """Upload lecture slides for exercise generation"""
    return await lecturer_service.upload_slides(file)

@router.post("/slides/generate", response_model=List[ExerciseResponse])
async def generate_exercises(slide_id: str = Form(...)):
    """Generate coding exercises from uploaded slides"""
    return await lecturer_service.generate_exercises(slide_id)


# EXERCISE MANAGEMENT

@router.get("/exercises", response_model=List[ExerciseResponse])
async def list_generated_exercises():
    """List all generated exercises (pending approval)"""
    return await lecturer_service.list_generated_exercises()

@router.put("/exercises/{exercise_id}/approve", response_model=ExerciseResponse)
async def approve_exercise(exercise_id: str):
    """Approve an exercise before publishing"""
    return await lecturer_service.approve_exercise(exercise_id)

@router.post("/exercises/publish")
async def publish_exercises(exercise_ids: List[str]):
    """Publish approved exercises to students"""
    return await lecturer_service.publish_exercises(exercise_ids)


# MODULE MANAGEMENT

@router.post("/modules", response_model=ModuleModel)
async def create_module(name: str = Form(...)):
    """Create a new module"""
    return await lecturer_service.create_module(name)

@router.get("/modules", response_model=List[ModuleModel])
async def list_modules():
    """List all modules"""
    return await lecturer_service.list_modules()

@router.post("/modules/{module_id}/students")
async def add_students_to_module(module_id: str, student_ids: List[str]):
    """Add students to a module"""
    return await lecturer_service.add_students_to_module(module_id, student_ids)

@router.delete("/modules/{module_id}/students/{student_id}")
async def remove_student_from_module(module_id: str, student_id: str):
    """Remove a student from a module"""
    return await lecturer_service.remove_student_from_module(module_id, student_id)

@router.post("/modules/{module_id}/assign")
async def assign_challenges_to_module(module_id: str, challenge_ids: List[str]):
    """Assign challenges to a module"""
    return await lecturer_service.assign_challenges_to_module(module_id, challenge_ids)


# ANALYTICS

@router.get("/analytics/module/{module_id}", response_model=AnalyticsResponse)
async def get_module_analytics(module_id: str):
    """Get performance analytics for a module"""
    return await lecturer_service.get_module_analytics(module_id)

@router.get("/analytics/export.csv")
async def export_module_analytics():
    """Export analytics data as CSV"""
    analytics = await lecturer_service.export_analytics()
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["module_id", "module_name", "avg_score", "completion_rate"])
    for a in analytics:
        writer.writerow([a["module_id"], a["module_name"], a["avg_score"], a["completion_rate"]])
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=analytics.csv"})
