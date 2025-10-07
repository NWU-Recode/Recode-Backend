# app/features/slidesDownload/repository.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from .models import Slide
from typing import List, Optional
from app.features.topic_detections.topics.models import Topic  # adjust path if needed
from app.features.challenges.models import Challenge

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


async def get_slides_by_challenge_id(db, challenge_id: str):
    query = text("""
        SELECT 
            se.id AS id,
            se.filename AS filename,
            c.week_number AS week_number,
            c.module_code AS module_code,
            t.id AS topic_id,
            t.title AS detected_topic,
            se.slides AS slides_key
        FROM 
            challenges c
        JOIN 
            topic t 
            ON t.week = c.week_number 
            AND t.module_code_slidesdeck = c.module_code
        JOIN 
            slide_extractions se 
            ON se.id = t.slide_extraction_id
        WHERE 
            c.id = :challenge_id
    """)
    result = await db.execute(query, {"challenge_id": challenge_id})
    return result.mappings().all()  



