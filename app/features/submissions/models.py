from sqlalchemy import Column, String, Text, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.DB.base import Base

class QuestionAttempt(Base):
    __tablename__ = "question_attempts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    challenge_id = Column(UUID(as_uuid=True), ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)  # Changed to Integer to match profiles.id
    judge0_token = Column(String(255), nullable=True)
    source_code = Column(Text, nullable=False)
    stdout = Column(Text, nullable=True)
    stderr = Column(Text, nullable=True)
    status_id = Column(Integer, nullable=False)
    status_description = Column(String(255), nullable=False)
    time = Column(String(50), nullable=True)
    memory = Column(Integer, nullable=True)
    is_correct = Column(Boolean, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    code_hash = Column(String(64), nullable=True)
    idempotency_key = Column(String(100), nullable=True)
    latest = Column(Boolean, nullable=False, default=True)
    def __repr__(self):
        return f"<QuestionAttempt(id={self.id}, question_id={self.question_id}, user_id={self.user_id})>"

class ChallengeAttempt(Base):
    __tablename__ = "challenge_attempts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    challenge_id = Column(UUID(as_uuid=True), ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)  # Changed to Integer to match profiles.id
    score = Column(Integer, nullable=False, default=0)
    total_correct = Column(Integer, nullable=False, default=0)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    def __repr__(self):
        return f"<ChallengeAttempt(id={self.id}, challenge_id={self.challenge_id}, user_id={self.user_id})>"
