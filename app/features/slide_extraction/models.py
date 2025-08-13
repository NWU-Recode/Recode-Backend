"""ORM models for the slide extraction feature."""

from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, JSON, String

from app.db.base import Base


class SlideExtraction(Base):
    """Persisted record of an extracted presentation."""

    __tablename__ = "slide_extractions"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    slides = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

