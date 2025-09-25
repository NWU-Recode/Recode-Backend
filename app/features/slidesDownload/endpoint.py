from typing import List, Optional, Any, Dict
import logging

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field

from app.DB.supabase import get_supabase
from app.features.topic_detections.slide_extraction.repository_supabase import (
    slide_extraction_supabase_repository,
)

router = APIRouter(prefix="/slides", tags=["SlidesDownload"])

DEFAULT_TTL = 900
MAX_TTL = 3600


class SlideMetadata(BaseModel):
    id: int
    filename: str
    week_number: Optional[int] = None
    module_code: Optional[str] = None
    topic_id: Optional[Any] = None
    has_file: bool = Field(False)


class SignedURLResponse(BaseModel):
    slide_id: int
    filename: Optional[str] = None
    signed_url: str
    expires_in: int


async def _fetch_slide_row_by_id(slide_id: int) -> Optional[Dict[str, Any]]:
    try:
        get_by_id = getattr(slide_extraction_supabase_repository, "get_by_id", None)
        if callable(get_by_id):
            row = await get_by_id(slide_id)
            if row is None:
                return None
            if isinstance(row, dict) and "data" in row and row.get("data"):
                return row.get("data")
            return row
    except Exception:
        logging.exception("slide_extraction_supabase_repository.get_by_id failed; falling back to query()")

    try:
        query = slide_extraction_supabase_repository.query()
        select_method = getattr(query, "select", None)
        if callable(select_method):
            query = query.select("id, filename, week_number, module_code, topic_id, slides_key")
        resp = await query.eq("id", slide_id).single().execute()
        if getattr(resp, "error", None):
            logging.debug("Supabase query error for slide %s: %s", slide_id, getattr(resp, "error"))
            return None
        data = getattr(resp, "data", None)
        if data:
            return data
        if isinstance(resp, dict):
            return resp
        return None
    except Exception:
        logging.exception("Fallback query for slide_by_id failed")
        return None


@router.get("/", response_model=List[SlideMetadata])
async def list_slides(
    week: Optional[int] = Query(None),
    module_code: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    try:
        query = slide_extraction_supabase_repository.query()
        if week is not None:
            query = query.eq("week_number", week)
        if module_code is not None:
            query = query.eq("module_code", module_code)
        if search:
            query = query.ilike("filename", f"%{search}%")

        select_method = getattr(query, "select", None)
        if callable(select_method):
            query = query.select("id, filename, week_number, module_code, topic_id, slides_key")

        slides_res = await query.execute()
        rows = getattr(slides_res, "data", None) or slides_res or []
    except Exception:
        logging.exception("Failed to fetch slides list")
        raise HTTPException(status_code=500, detail="Failed to fetch slides")

    out: List[SlideMetadata] = []
    for r in rows:
        out.append(
            SlideMetadata(
                id=r.get("id"),
                filename=r.get("filename") or "",
                week_number=r.get("week_number"),
                module_code=r.get("module_code"),
                topic_id=r.get("topic_id"),
                has_file=bool(r.get("slides_key")),
            )
        )
    return out


@router.get("/{slide_id}", response_model=SlideMetadata)
async def get_slide_by_id(slide_id: int):
    row = await _fetch_slide_row_by_id(slide_id)
    if not row:
        raise HTTPException(status_code=404, detail="Slide not found")

    return SlideMetadata(
        id=row.get("id"),
        filename=row.get("filename") or "",
        week_number=row.get("week_number"),
        module_code=row.get("module_code"),
        topic_id=row.get("topic_id"),
        has_file=bool(row.get("slides_key")),
    )


@router.get("/{slide_id}/download", response_model=SignedURLResponse)
async def download_slide(slide_id: int, ttl: int = Query(DEFAULT_TTL)):
    if ttl <= 0 or ttl > MAX_TTL:
        raise HTTPException(status_code=400, detail=f"ttl must be between 1 and {MAX_TTL} seconds")

    client = await get_supabase()

    row = await _fetch_slide_row_by_id(slide_id)
    if not row:
        raise HTTPException(status_code=404, detail="Slide not found")

    key = row.get("slides_key")
    if not key:
        raise HTTPException(status_code=404, detail="Slide storage key missing")

    try:
        bucket = client.storage.from_("slides")
        signed = await bucket.create_signed_url(key, expires_in=ttl)
        signed_url = None
        if isinstance(signed, dict):
            signed_url = signed.get("signedURL") or signed.get("signed_url") or signed.get("signedUrl")
            if signed_url is None and isinstance(signed.get("data"), dict):
                signed_url = signed["data"].get("signedURL") or signed["data"].get("signed_url")
        else:
            try:
                signed_url = getattr(signed, "get", None) and (signed.get("signedURL") or signed.get("signed_url") or signed.get("signedUrl"))
            except Exception:
                signed_url = None

        if not signed_url:
            logging.debug("create_signed_url returned: %s", signed)
            raise Exception("No signed URL in storage response")
    except HTTPException:
        raise
    except Exception:
        logging.exception("Failed to generate signed URL for slide %s", slide_id)
        raise HTTPException(status_code=500, detail="Failed to generate signed URL")

    return SignedURLResponse(slide_id=slide_id, filename=row.get("filename"), signed_url=signed_url, expires_in=ttl)