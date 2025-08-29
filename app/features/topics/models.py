from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import relationship
from app.DB.base import Base
from app.DB.models import Challenge

class Topic(Base):
    id = Column(Integer, primary_key=True, index=True)
    week = Column(Integer, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    challenges = relationship("Challenge", back_populates="topic")
