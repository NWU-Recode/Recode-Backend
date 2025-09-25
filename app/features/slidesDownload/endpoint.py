from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional, Dict, Any
from app.DB.supabase import get_supabase
from app.features.topic_detections.slide_extraction.repository_supabase import (
    slide_extraction_supabase_repository,
)

router = APIRouter(prefix="/slides", tags=["SlidesDownload"])


@router.get("/", response_model=List[Dict[str, Any]])
async def list_slides(
    week: Optional[int] = Query(None, description="Filter by week number"),
    module_code: Optional[str] = Query(None, description="Filter by module code"),
    search: Optional[str] = Query(None, description="Search by filename (ILIKE)"),
    signed_url_ttl_sec: int = Query(900, description="TTL for signed download links (seconds)"),
):
    """
    List slides from Supabase.
    - Filters: week, module_code, search text
    - Returns signed URLs so frontend can download and cache offline
    """

    client = await get_supabase()

    try:
        query = slide_extraction_supabase_repository.query()
        if week is not None:
            query = query.eq("week_number", week)
        if module_code is not None:
            query = query.eq("module_code", module_code)
        if search:
            query = query.ilike("filename", f"%{search}%")

        slides_res = await query.execute()
        rows = slides_res.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch slides: {str(e)}")

    bucket = client.storage.from_("slides")
    output: List[Dict[str, Any]] = []

    for row in rows:
        key = row.get("slides_key")
        signed_url = None

        if key:
            try:
                signed = await bucket.create_signed_url(key, expires_in=signed_url_ttl_sec)
                if isinstance(signed, dict):
                    signed_url = signed.get("signedURL") or signed.get("signed_url") or signed.get("signedUrl")
            except Exception:
                signed_url = None

        output.append({
            "id": row.get("id"),
            "filename": row.get("filename"),
            "week_number": row.get("week_number"),
            "module_code": row.get("module_code"),
            "topic_id": row.get("topic_id"),
            "slides_key": key,
            "signed_url": signed_url,
        })

    return output


@router.get("/{slide_id}/download")
async def download_slide(slide_id: int, ttl: int = Query(900, description="TTL for signed download link (seconds)")):
    """
    Fetch a single slide by ID and return a fresh signed download URL.
    Useful for direct download on the frontend.
    """
    client = await get_supabase()

    # Lookup row in slide_extractions table
    try:
        row = await slide_extraction_supabase_repository.get_by_id(slide_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query slide: {str(e)}")

    if not row:
        raise HTTPException(status_code=404, detail="Slide not found")

    key = row.get("slides_key")
    if not key:
        raise HTTPException(status_code=404, detail="Slide key missing")

    # Generate signed URL
    try:
        signed = await client.storage.from_("slides").create_signed_url(key, expires_in=ttl)
        signed_url = None
        if isinstance(signed, dict):
            signed_url = signed.get("signedURL") or signed.get("signed_url") or signed.get("signedUrl")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate signed URL: {str(e)}")

    if not signed_url:
        raise HTTPException(status_code=404, detail="Unable to create signed URL")

    return {"slide_id": slide_id, "signed_url": signed_url, "expires_in": ttl}
