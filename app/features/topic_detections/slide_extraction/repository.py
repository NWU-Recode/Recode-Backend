
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from app.DB.session import get_db
from .models import SlideExtraction
from .schemas import SlideExtractionCreate


class SlideExtractionRepository:
    """SQLAlchemy-based repository for slide extractions."""

    def create_extraction(self, data: SlideExtractionCreate) -> SlideExtraction:
        """Create a new slide extraction record."""
        db = next(get_db())
        try:
            record = SlideExtraction(
                filename=data.filename,
                slides_key=getattr(data, "slides_key", None),
                slides=data.slides,
                created_at=data.created_at if hasattr(data, "created_at") else datetime.now(timezone.utc)
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return record
        except Exception as e:
            db.rollback()
            raise RuntimeError(f"Failed to create slide extraction record: {e}")
        finally:
            db.close()

    def list_extractions(self, offset: int = 0, limit: int = 50) -> List[SlideExtraction]:
        """List slide extractions with pagination."""
        db = next(get_db())
        try:
            return db.query(SlideExtraction).order_by(
                desc(SlideExtraction.id)
            ).offset(offset).limit(limit).all()
        finally:
            db.close()

    def count_extractions(self) -> int:
        """Count total number of slide extractions."""
        db = next(get_db())
        try:
            return db.query(SlideExtraction).count()
        finally:
            db.close()

    def get_extraction(self, extraction_id: int) -> Optional[SlideExtraction]:
        """Get slide extraction by ID."""
        db = next(get_db())
        try:
            return db.query(SlideExtraction).filter(
                SlideExtraction.id == extraction_id
            ).first()
        finally:
            db.close()

    def delete_extraction(self, extraction_id: int) -> bool:
        """Delete slide extraction by ID."""
        db = next(get_db())
        try:
            extraction = db.query(SlideExtraction).filter(
                SlideExtraction.id == extraction_id
            ).first()
            
            if not extraction:
                return False
                
            db.delete(extraction)
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise RuntimeError(f"Failed to delete extraction: {e}")
        finally:
            db.close()

    def get_extractions_by_filename(self, filename: str) -> List[SlideExtraction]:
        """Get extractions by filename."""
        db = next(get_db())
        try:
            return db.query(SlideExtraction).filter(
                SlideExtraction.filename == filename
            ).order_by(desc(SlideExtraction.created_at)).all()
        finally:
            db.close()

    def update_extraction(self, extraction_id: int, update_data: Dict[str, Any]) -> Optional[SlideExtraction]:
        """Update slide extraction fields."""
        db = next(get_db())
        try:
            extraction = db.query(SlideExtraction).filter(
                SlideExtraction.id == extraction_id
            ).first()
            
            if not extraction:
                return None
                
            for key, value in update_data.items():
                if hasattr(extraction, key):
                    setattr(extraction, key, value)
                    
            db.commit()
            db.refresh(extraction)
            return extraction
        except Exception as e:
            db.rollback()
            raise RuntimeError(f"Failed to update extraction: {e}")
        finally:
            db.close()


# Repository instance
slide_extraction_repository = SlideExtractionRepository()
