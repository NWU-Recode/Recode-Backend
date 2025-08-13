"""API endpoints for slide extraction."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query, Path
from sqlalchemy.orm import Session

from app.db.session import get_db
from .schemas import SlideExtractionRead
from .service import save_extraction_from_upload
from . import repository


router = APIRouter(prefix="/slides", tags=["slide-extraction"])


@router.post("/extract", response_model=SlideExtractionRead)
async def extract_slides(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    persist: bool = Query(True, description="Persist result in DB (true) or just return raw data (false)"),
) -> SlideExtractionRead | dict:
    try:
        return await save_extraction_from_upload(file, db, persist=persist)  # type: ignore[return-value]
    except ValueError as exc:  # pragma: no cover
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/", response_model=list[SlideExtractionRead])
async def list_slide_extractions(
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200)
) -> list[SlideExtractionRead]:
    """List stored slide extraction records (paginated)."""
    return repository.list_extractions(db, offset=offset, limit=limit)

@router.get("/{extraction_id}", response_model=SlideExtractionRead)
async def get_slide_extraction(
    extraction_id: int = Path(..., ge=1),
    db: Session = Depends(get_db)
) -> SlideExtractionRead:
    record = repository.get_extraction(db, extraction_id)
    if not record:
        raise HTTPException(status_code=404, detail="Extraction not found")
    return record  # type: ignore[return-value]

@router.delete("/{extraction_id}", response_model=dict)
async def delete_slide_extraction(
    extraction_id: int = Path(..., ge=1),
    db: Session = Depends(get_db)
) -> dict:
    if not repository.delete_extraction(db, extraction_id):
        raise HTTPException(status_code=404, detail="Extraction not found")
    return {"deleted": extraction_id}

@router.post("/extract/raw", response_model=dict)
async def extract_slides_raw(file: UploadFile = File(...)) -> dict:
    """Extract slide text without hitting the database (quick test endpoint)."""
    try:
        # Re-use logic without DB dependency (pass persist False and a dummy session placeholder)
        # We call lower-level helper by opening a transient sessionless path.
        from .service import extract_slides_from_upload
        slides = await extract_slides_from_upload(file)
        return {"filename": file.filename, "slides": slides}
    except ValueError as exc:  # pragma: no cover
        raise HTTPException(status_code=400, detail=str(exc))
