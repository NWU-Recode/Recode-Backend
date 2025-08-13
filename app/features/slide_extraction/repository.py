"""Database operations for slide extraction records."""

from sqlalchemy.orm import Session

from . import models, schemas


def create_extraction(
    db: Session, data: schemas.SlideExtractionCreate
) -> models.SlideExtraction:
    """Persist a new slide extraction record."""
    record = models.SlideExtraction(filename=data.filename, slides=data.slides)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_extractions(db: Session) -> list[models.SlideExtraction]:
    """Return all stored slide extractions."""
    return db.query(models.SlideExtraction).order_by(models.SlideExtraction.id).all()
