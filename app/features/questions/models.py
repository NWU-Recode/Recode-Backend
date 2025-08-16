from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.DB.base import Base

import enum
class QuestionTier(enum.Enum):
    bronze = "bronze"
    silver = "silver"
    gold = "gold"
    ruby = "ruby"
    emerald = "emerald"
    diamond = "diamond"

class Question(Base):
    __tablename__ = "questions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    challenge_id = Column(UUID(as_uuid=True), ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False)
    language_id = Column(Integer, nullable=False)
    expected_output = Column(Text, nullable=True)
    points = Column(Integer, nullable=False, default=0)
    starter_code = Column(Text, nullable=True)
    max_time_ms = Column(Integer, nullable=True)
    max_memory_kb = Column(Integer, nullable=True)
    tier = Column(Enum(QuestionTier), nullable=False, default=QuestionTier.bronze)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<Question(id={self.id}, challenge_id={self.challenge_id}, tier={self.tier})>"
