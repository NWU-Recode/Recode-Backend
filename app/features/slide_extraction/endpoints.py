"""API endpoints for slide extraction."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from .schemas import SlideExtractionRead
from .service import save_extraction_from_upload


router = APIRouter(prefix="/slides", tags=["slide-extraction"])


@router.post("/extract", response_model=SlideExtractionRead)
async def extract_slides(
    file: UploadFile = File(...), db: Session = Depends(get_db)
) -> SlideExtractionRead:
    """Extract text from the uploaded PowerPoint presentation."""
    try:
        return await save_extraction_from_upload(file, db)
    except ValueError as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=400, detail=str(exc))
