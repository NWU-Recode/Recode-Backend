from __future__ import annotations

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional, Dict, Any
from .service import generate_week


router = APIRouter(prefix="/weeks", tags=["weeks"])


class GenerateRequest(BaseModel):
    slides_url: str
    force: bool = False


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
