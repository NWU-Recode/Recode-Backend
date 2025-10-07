# app/features/slidesDownload/models.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

Base = declarative_base()  

class Slide(Base):
    __tablename__ = "slide_extractions"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    slides_key = Column(String, nullable=True)
    week_number = Column(Integer, nullable=True)
    module_code = Column(String, nullable=True)
    topic_id = Column(String, nullable=True)
    detected_topic = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())




