from typing import List, Optional
from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.DB.session import get_db
from . import service
from . import schemas


router = APIRouter(prefix="/slides", tags=["SlidesDownload"])


@router.get("/", response_model=List[schemas.SlideMetadata])
async def list_slides_endpoint(
    week: Optional[List[int]] = Query(None),
    module_code: Optional[List[str]] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    slides = await service.list_slides(
        db=db, weeks=week, module_codes=module_code, search=search
    )
    return [
    schemas.SlideMetadata(
        id=s.id,
        filename=s.filename or "",
        week_number=s.week_number,
        module_code=s.module_code,
        topic_id=s.topic_id,
        has_file=bool(s.slides_key),
        detected_topic=s.detected_topic,  
    )
    for s in slides
]


@router.get("/{slide_id}", response_model=schemas.SlideMetadata)
async def get_slide(slide_id: int, db: AsyncSession = Depends(get_db)):
    slide = await service.fetch_slide_by_id(db=db, slide_id=slide_id)
    if not slide:
        raise HTTPException(status_code=404, detail="Slide not found")
    return schemas.SlideMetadata(
        id=slide.id,
        filename=slide.filename,
        week_number=slide.week_number,
        module_code=slide.module_code,
        topic_id=slide.topic_id,
        detected_topic=slide.detected_topic,
        has_file=bool(slide.slides_key),
    )


@router.get("/{slide_id}/download", response_model=schemas.SignedURLResponse)
async def download_slide(slide_id: int, ttl: int = 300, db: AsyncSession = Depends(get_db)):
    slide = await service.fetch_slide_by_id(db=db, slide_id=slide_id)
    if not slide or not slide.slides_key:
        raise HTTPException(status_code=404, detail="Slide not found or no file attached")

    url = await service.generate_signed_url(slide.slides_key, ttl)
    return schemas.SignedURLResponse(
        slide_id=slide.id,
        filename=slide.filename,
        signed_url=url,
        expires_in=ttl,
    )


