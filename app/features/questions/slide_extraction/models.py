from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
import uuid
from app.DB.base import Base


class SlideExtraction(Base):
    __tablename__ = "slide_extractions"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    slides = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

