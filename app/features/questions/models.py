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
    challenge_id = Column(UUID(as_uuid=True), ForeignKey("challenges.id", ondelete="CASCADE"), nullable=True)
    language_id = Column(Integer, nullable=False)
    expected_output = Column(Text, nullable=True)
    points = Column(Integer, nullable=False, default=0)
    starter_code = Column(Text, nullable=True)
    max_time_ms = Column(Integer, nullable=True)
    max_memory_kb = Column(Integer, nullable=True)
    tier = Column(Enum(QuestionTier), nullable=False, default=QuestionTier.bronze)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    topic = Column(String, nullable=True)

#since a question can be in many challenges and a challenge can have many questions (MANY:MANY)
class ChallengeQuestion(Base):
    __tablename__ = "challenge_questions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    challenge_id = Column(UUID(as_uuid=True), ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)

#For /stats 
class QuestionUsage(Base):
    __tablename__ = "question_usage"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    challenge_id = Column(UUID(as_uuid=True), ForeignKey("challenges.id", ondelete="CASCADE"), nullable=True)
    times_attempted = Column(Integer, default=0)
    times_passed = Column(Integer, default=0)

#A question can have many hints
class QuestionHint(Base):
    __tablename__ = "question_hints"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    tier = Column(Enum(QuestionTier), nullable=False)



    def __repr__(self):
        return f"<Question(id={self.id}, challenge_id={self.challenge_id}, tier={self.tier})>"
