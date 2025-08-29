from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
import uuid
from app.DB.base import Base


class SlideExtraction(Base):
    __tablename__ = "slide_extractions"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    # Storage object key relative to bucket (e.g., 2025S2/w03/topic/ts-uuid-file.pptx)
    slides_key = Column(String, nullable=True)
    slides = Column(JSONB, nullable=False)
    detected_topic = Column(String, nullable=True)
    detected_subtopics = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

