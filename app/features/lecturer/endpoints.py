from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from io import StringIO
import csv
from app.common.deps import require_role, CurrentUser
from .service import lecturer_service

router = APIRouter(prefix="/lecturer", tags=["lecturer"])

@router.get("/students")
async def list_students(current: CurrentUser = Depends(require_role("lecturer"))):
    return await lecturer_service.list_students_with_progress()

@router.get("/students/export.csv")
async def export_students_csv(current: CurrentUser = Depends(require_role("lecturer"))):
    rows = await lecturer_service.list_students_with_progress()
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["student_id","email","plain_pct","ruby","emerald","diamond","blended_pct"])
    for r in rows:
        writer.writerow([
            r.get("id"),
            r.get("email"),
            r.get("plain_pct"),
            int(r.get("ruby_correct")),
            int(r.get("emerald_correct")),
            int(r.get("diamond_correct")),
            r.get("blended_pct"),
        ])
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="text/csv", headers={"Content-Disposition":"attachment; filename=students_progress.csv"})
