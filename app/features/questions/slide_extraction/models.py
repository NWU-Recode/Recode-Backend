# Stub SQLAlchemy model for SlideExtraction to prevent import errors
from app.DB.base import Base
from sqlalchemy import Column, Integer, String

class SlideExtraction(Base):
    __tablename__ = "slide_extraction"
    id = Column(Integer, primary_key=True, autoincrement=True)
    slide_id = Column(String, nullable=False)
    text = Column(String, nullable=True)
