from sqlalchemy.orm import Session
from sqlalchemy import select

from . import models, schemas


def create_extraction(db: Session, data: schemas.SlideExtractionCreate) -> models.SlideExtraction:
    """Persist a new slide extraction record."""
    record = models.SlideExtraction(filename=data.filename, slides=data.slides)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_extractions(db: Session, *, offset: int = 0, limit: int = 50) -> list[models.SlideExtraction]:
    """Return stored slide extractions with pagination."""
    stmt = (
        select(models.SlideExtraction)
        .order_by(models.SlideExtraction.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def count_extractions(db: Session) -> int:
    return db.query(models.SlideExtraction).count()


def get_extraction(db: Session, extraction_id: int) -> models.SlideExtraction | None:
    return db.get(models.SlideExtraction, extraction_id)


def delete_extraction(db: Session, extraction_id: int) -> bool:
    record = get_extraction(db, extraction_id)
    if not record:
        return False
    db.delete(record)
    db.commit()
    return True
