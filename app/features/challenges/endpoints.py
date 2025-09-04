from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends
from app.common.deps import require_lecturer
from .service import (
    generate_weekly_challenge,
    generate_special_challenge,
    generate_semester_challenges,
)

router = APIRouter(prefix="/challenges", tags=["challenges"])

@router.post("/week/{week}")
async def create_weekly(week: int, force: bool = False, current=Depends(require_lecturer())):
    try:
        return await generate_weekly_challenge(week, lecturer_id=current.id, force=force)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/semester")
async def create_semester(force: bool = False, current=Depends(require_lecturer())):
    try:
        return await generate_semester_challenges(lecturer_id=current.id, force=force)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/special/{kind}/{week}")
async def create_special(kind: str, week: int, force: bool = False, current=Depends(require_lecturer())):
    try:
        return await generate_special_challenge(kind.lower(), week, lecturer_id=current.id, force=force)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
