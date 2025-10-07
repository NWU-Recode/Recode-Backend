from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from app.DB.base import Base


class Topic(Base):
    __tablename__ = "topic"
    id = Column(Integer, primary_key=True, index=True)
    week = Column(Integer, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    subtopics = Column(JSONB, nullable=True)
    module_code_slidesdeck = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    
    challenges = relationship("Challenge", back_populates="topic")
