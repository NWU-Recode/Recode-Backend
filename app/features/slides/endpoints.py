from __future__ import annotations

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query
from datetime import datetime, date, time, timedelta
from typing import List
import asyncio

from app.common.deps import get_current_user_from_cookie, CurrentUser
from app.common.deps import require_admin_or_lecturer_cookie
from .upload import upload_slide_bytes
from .pathing import parse_week_topic_from_filename, SA_TZ

router = APIRouter(prefix="/slides", tags=["slides"])

# Set per deployment/season
SEMESTER_START = date(2025, 7, 7)


@router.post("/upload")
async def upload_slide(
    module_code: str = Query(..., description="Module code for the slides"),
    topic_name: str | None = Query(None, description="Optional topic override; inferred from filename/slides if omitted"),
    given_at_iso: str | None = Query(None, description="Optional ISO datetime; inferred from filename week or uses now if omitted"),
    include_signed_url: bool = Query(False, description="Include a short-lived signed URL in the response (not stored)"),
    signed_ttl_sec: int = Query(900, ge=60, le=86400, description="TTL (seconds) for the signed URL if requested"),
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_admin_or_lecturer_cookie()),
):
    try:
        data = await file.read()
        # Parse optional inputs from filename if not provided
        parsed_week, parsed_topic = parse_week_topic_from_filename(file.filename)
        tn = topic_name or parsed_topic or "Topic"
        if given_at_iso:
            given_at_dt = datetime.fromisoformat(given_at_iso)
        elif parsed_week:
            # Map week number to a date within that week relative to semester start
            target_date = SEMESTER_START + timedelta(weeks=max(1, min(12, parsed_week)) - 1)
            given_at_dt = datetime.combine(target_date, time(10, 0, 0, tzinfo=SA_TZ))
        else:
            given_at_dt = datetime.now(tz=SA_TZ)
        out = await upload_slide_bytes(
            data, file.filename, tn, given_at_dt, SEMESTER_START, signed_url_ttl_sec=signed_ttl_sec, module_code=module_code
        )
        # Do not expose signed URL unless explicitly requested
        if not include_signed_url:
            out.pop("signed_url", None)
        return out
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/batch-upload")
async def batch_upload_slides(
    module_code: str = Query(..., description="Module code for all slides"),
    topic_name: str | None = Query(None, description="Optional topic override; inferred from filename/slides if omitted"),
    include_signed_url: bool = Query(False, description="Include a short-lived signed URL in the response (not stored)"),
    signed_ttl_sec: int = Query(900, ge=60, le=86400, description="TTL (seconds) for the signed URL if requested"),
    files: List[UploadFile] = File(...),
    current_user: CurrentUser = Depends(require_admin_or_lecturer_cookie()),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    # Limit concurrency to prevent overwhelming the server/storage
    semaphore = asyncio.Semaphore(14)  # Max 14 concurrent uploads
    
    async def process_file(file: UploadFile):
        async with semaphore:
            try:
                data = await file.read()
                # Parse optional inputs from filename if not provided
                parsed_week, parsed_topic = parse_week_topic_from_filename(file.filename)
                tn = topic_name or parsed_topic or "Topic"
                if parsed_week:
                    # Map week number to a date within that week relative to semester start
                    target_date = SEMESTER_START + timedelta(weeks=max(1, min(12, parsed_week)) - 1)
                    given_at_dt = datetime.combine(target_date, time(10, 0, 0, tzinfo=SA_TZ))
                else:
                    given_at_dt = datetime.now(tz=SA_TZ)
                result = await upload_slide_bytes(
                    data, file.filename, tn, given_at_dt, SEMESTER_START, signed_url_ttl_sec=signed_ttl_sec, module_code=module_code
                )
                # Do not expose signed URL unless explicitly requested
                if not include_signed_url:
                    result.pop("signed_url", None)
                return {"filename": file.filename, "success": True, "data": result}
            except Exception as e:
                return {"filename": file.filename, "success": False, "error": str(e)}
    
    # Process all files concurrently with controlled concurrency
    tasks = [process_file(file) for file in files]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle any unexpected exceptions in gather
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed_results.append({"filename": files[i].filename, "success": False, "error": str(result)})
        else:
            processed_results.append(result)
    
    return {"results": processed_results}
