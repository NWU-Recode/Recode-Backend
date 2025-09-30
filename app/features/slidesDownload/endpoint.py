from typing import List, Optional, Any, Dict
import logging
import inspect

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import httpx

from app.DB.supabase import get_supabase

logger = logging.getLogger(__name__)

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


def _extract_signed_url(signed: Any) -> Optional[str]:
    if not signed:
        return None

    try:
        if isinstance(signed, dict):
            for key in ("signedURL", "signed_url", "signedUrl", "url"):
                val = signed.get(key)
                if val:
                    return val
            data = signed.get("data")
            if isinstance(data, dict):
                for key in ("signedURL", "signed_url", "signedUrl", "url"):
                    if data.get(key):
                        return data.get(key)
            return None

        get = getattr(signed, "get", None)
        if callable(get):
            try:
                for key in ("signedURL", "signed_url", "signedUrl", "url"):
                    val = signed.get(key)
                    if val:
                        return val
                data = signed.get("data")
                if isinstance(data, dict):
                    for key in ("signedURL", "signed_url", "signedUrl", "url"):
                        if data.get(key):
                            return data.get(key)
            except Exception:
                pass

        for attr in ("signedURL", "signed_url", "signedUrl", "url"):
            if hasattr(signed, attr):
                val = getattr(signed, attr)
                if val:
                    return val

        s = str(signed)
        if s.startswith("http"):
            return s
    except Exception:
        logging.exception("_extract_signed_url failed to parse storage response")

    return None


async def _fetch_slide_row_by_id(slide_id: int) -> Optional[Dict[str, Any]]:
    try:
        client = await get_supabase()
        query = client.table("slide_extractions").select(
            "id, filename, week_number, module_code, topic_id, slides_key"
        ).eq("id", slide_id).single()

        resp = await query.execute()
        data = getattr(resp, "data", None) or (resp.get("data") if isinstance(resp, dict) else None)
        return data
    except Exception:
        logger.exception("Failed to fetch slide by id")
        return None


@router.get("/", response_model=List[SlideMetadata])
async def list_slides(
    week: Optional[int] = Query(None),
    module_code: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    try:
        client = await get_supabase()
        query = client.table("slide_extractions").select(
            "id, filename, week_number, module_code, topic_id, slides_key"
        )

        if week is not None:
            query = query.eq("week_number", week)
        if module_code is not None:
            query = query.eq("module_code", module_code)
        if search:
            query = query.ilike("filename", f"%{search}%")

        slides_res = await query.execute()
        rows = getattr(slides_res, "data", None) or (slides_res.get("data") if isinstance(slides_res, dict) else []) or []

    except Exception:
        logger.exception("Failed to fetch slides list")
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
        signed = bucket.create_signed_url(key, expires_in=ttl)

        if inspect.isawaitable(signed):
            signed = await signed

        signed_url = _extract_signed_url(signed)
        if not signed_url:
            logger.debug("create_signed_url returned: %s", signed)
            raise Exception("No signed URL in storage response")
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to generate signed URL for slide %s", slide_id)
        raise HTTPException(status_code=500, detail="Failed to generate signed URL")

    return SignedURLResponse(slide_id=slide_id, filename=row.get("filename"), signed_url=signed_url, expires_in=ttl)


@router.get("/{slide_id}/download-file", response_class=StreamingResponse)
async def download_slide_file(slide_id: int, ttl: int = Query(DEFAULT_TTL)):
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
        signed = bucket.create_signed_url(key, expires_in=ttl)
        if inspect.isawaitable(signed):
            signed = await signed
        signed_url = _extract_signed_url(signed)
        if not signed_url:
            logger.debug("create_signed_url returned: %s", signed)
            raise Exception("No signed URL in storage response")
    except Exception:
        logger.exception("Failed to generate signed URL for slide %s", slide_id)
        raise HTTPException(status_code=500, detail="Failed to generate signed URL")

    try:
        async with httpx.AsyncClient() as http:
            resp = await http.get(signed_url, timeout=60.0)
            if resp.status_code != 200:
                logger.debug("Failed to fetch file from signed URL: %s (status=%s)", signed_url, resp.status_code)
                raise HTTPException(status_code=502, detail="Failed to fetch slide file from storage provider")

            media_type = resp.headers.get("content-type", "application/octet-stream")
            filename = (row.get("filename") or "slide")
            headers = {"Content-Disposition": f'attachment; filename=\"{filename}\"'}

            return StreamingResponse(resp.aiter_bytes(), media_type=media_type, headers=headers)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error while streaming slide file for slide %s", slide_id)
        raise HTTPException(status_code=500, detail="Failed to stream slide file")
