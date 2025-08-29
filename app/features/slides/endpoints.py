from __future__ import annotations

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from datetime import datetime, date

from app.common.deps import get_current_user_from_cookie, CurrentUser
from app.common.deps import require_admin_or_lecturer_cookie
from .upload import upload_slide_bytes

router = APIRouter(prefix="/slides", tags=["slides"])

# Set per deployment/season
SEMESTER_START = date(2025, 7, 7)


@router.post("/upload")
async def upload_slide(
    topic_name: str,
    given_at_iso: str,
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_admin_or_lecturer_cookie()),
):
    try:
        data = await file.read()
        given_at_dt = datetime.fromisoformat(given_at_iso)
        out = await upload_slide_bytes(
            data, file.filename, topic_name, given_at_dt, SEMESTER_START
        )
        return out
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

