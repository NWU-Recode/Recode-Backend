from __future__ import annotations

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional, Dict, Any


router = APIRouter(prefix="/weeks", tags=["weeks"])


class GenerateRequest(BaseModel):
    slides_url: str


@router.post("/{week_number}/generate")
async def generate_week(week_number: int, req: GenerateRequest):
    """Generate a week from slides (scaffold).

    Returns a minimal payload consistent with the smoke test expectations.
    """
    if week_number <= 0:
        raise HTTPException(status_code=400, detail={"error_code": "E_INVALID_WEEK", "message": "week must be > 0"})

    # Derive a simple slug from slides URL
    import re
    base = req.slides_url.strip().split("/")[-1] or "topic"
    base = re.sub(r"\.[A-Za-z0-9]+$", "", base)  # strip extension
    normalized = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-") or "topic"
    slug = f"w{week_number:02d}-{normalized}"

    # Stub a UUID-like id for created challenge to satisfy smoke test shape
    import uuid
    common_id = str(uuid.uuid4())

    return {
        "topic": {"slug": slug},
        "created": {
            "common": {"challenge_id": common_id}
        },
        "status": "draft"
    }


@router.post("/{week_number}/publish")
async def publish_week(week_number: int):
    if week_number <= 0:
        raise HTTPException(status_code=400, detail={"error_code": "E_INVALID_WEEK", "message": "week must be > 0"})
    return {"week": week_number, "status": "published"}

