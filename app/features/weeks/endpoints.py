from __future__ import annotations

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional, Dict, Any
from .service import generate_week
from app.features.slides.pathing import parse_week_topic_from_filename
import re


router = APIRouter(prefix="/weeks", tags=["weeks"])


class GenerateRequest(BaseModel):
    slides_url: str
    force: bool = False


@router.post("/generate")
async def generate_week_auto(req: GenerateRequest):
    """Generate a week from slides without specifying week in the path.

    Derives week from slides_url (e.g., supabase://slides/.../w03/...) or from
    the filename (e.g., Week3_Conditionals.pptx). Fails if no week can be found.
    """
    week_number: Optional[int] = None
    # Try to extract /wNN/ from the path
    m = re.search(r"/w(\d{2})/", req.slides_url)
    if m:
        try:
            week_number = int(m.group(1))
        except Exception:
            week_number = None
    if week_number is None:
        # Fallback: last path segment filename
        path_part = req.slides_url
        if req.slides_url.startswith("supabase://"):
            # supabase://<bucket>/<object_key>
            rest = req.slides_url.split("://", 1)[1]
            parts = rest.split("/", 1)
            object_key = parts[1] if len(parts) == 2 else parts[0]
            filename = object_key.split("/")[-1]
        else:
            filename = req.slides_url.split("/")[-1]
        derived, _ = parse_week_topic_from_filename(filename)
        if derived:
            week_number = int(derived)
    if not week_number:
        raise HTTPException(status_code=400, detail={
            "error_code": "E_INVALID_INPUT",
            "message": "Could not derive week from slides_url. Include /wNN/ in the path or use filename 'Week{n}_...'."
        })
    return await generate_week(week_number, req.slides_url, req.force)


@router.post("/{week_number}/generate")
async def generate_week_endpoint(week_number: int, req: GenerateRequest):
    """Generate a week from slides (scaffold).

    Returns a minimal payload consistent with the smoke test expectations.
    """
    if week_number <= 0:
        raise HTTPException(status_code=400, detail={"error_code": "E_INVALID_WEEK", "message": "week must be > 0"})

    # Delegate to service orchestrator
    result = await generate_week(week_number, req.slides_url, req.force)
    return result


@router.post("/{week_number}/publish")
async def publish_week(week_number: int):
    if week_number <= 0:
        raise HTTPException(status_code=400, detail={"error_code": "E_INVALID_WEEK", "message": "week must be > 0"})
    return {"week": week_number, "status": "published"}
