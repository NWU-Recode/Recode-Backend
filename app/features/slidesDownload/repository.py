# app/features/slidesDownload/repository.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .models import Slide
from typing import List, Optional

async def get_slide_by_id(db: AsyncSession, slide_id: int) -> Optional[Slide]:
    result =  db.execute(select(Slide).where(Slide.id == slide_id))
    return result.scalar_one_or_none()

async def list_slides(
    db: AsyncSession,
    weeks: Optional[List[int]] = None,
    module_codes: Optional[List[str]] = None,
    search: Optional[str] = None,
) -> List[Slide]:
    query = select(Slide)
    if weeks:
        query = query.where(Slide.week_number.in_(weeks))
    if module_codes:
        query = query.where(Slide.module_code.in_(module_codes))
    if search:
        # search both filename and detected_topic
        query = query.where(
            (Slide.filename.ilike(f"%{search}%")) |
            (Slide.detected_topic.ilike(f"%{search}%"))
        )
    result =  db.execute(query)
    return result.scalars().all()
