from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
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
    is_active = Column(Boolean, default=True, nullable=False)
    question_text = Column(Text, nullable=True)  # The actual question content
    atomic_tests_json = Column(JSONB, nullable=True)  # Test cases in JSON format
    canonical_solution = Column(Text, nullable=True)  # Reference solution
    
    # Relationships
    hints = relationship("QuestionHint", back_populates="question", cascade="all, delete-orphan")
    attempts = relationship("QuestionAttempt", back_populates="question", cascade="all, delete-orphan")

class ChallengeQuestion(Base):
    __tablename__ = "challenge_questions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    challenge_id = Column(UUID(as_uuid=True), ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    order_index = Column(Integer, nullable=False, default=0)  # Order within challenge
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class QuestionUsage(Base):
    __tablename__ = "question_usage"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    challenge_id = Column(UUID(as_uuid=True), ForeignKey("challenges.id", ondelete="CASCADE"), nullable=True)
    times_attempted = Column(Integer, default=0)
    times_passed = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class QuestionHint(Base):
    __tablename__ = "question_hints"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    tier = Column(Enum(QuestionTier), nullable=False)
    order_index = Column(Integer, nullable=False, default=0)  # Order of hints
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationship
    question = relationship("Question", back_populates="hints")

class QuestionAttempt(Base):
    __tablename__ = "question_attempts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    challenge_id = Column(UUID(as_uuid=True), ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False)
    challenge_attempt_id = Column(UUID(as_uuid=True), ForeignKey("challenge_attempts.id", ondelete="CASCADE"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    judge0_token = Column(String(255), nullable=True)
    source_code = Column(Text, nullable=False)
    stdin = Column(Text, nullable=True)
    stdout = Column(Text, nullable=True)
    stderr = Column(Text, nullable=True)
    status_id = Column(Integer, nullable=False)
    status_description = Column(String(255), nullable=False)
    time = Column(String(50), nullable=True)  # execution time
    memory = Column(Integer, nullable=True)  # memory used
    is_correct = Column(Boolean, nullable=True)  # null = not graded yet
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    code_hash = Column(String(64), nullable=True)  # for deduplication
    idempotency_key = Column(String(100), nullable=True)  # for preventing duplicate submissions
    latest = Column(Boolean, nullable=False, default=True)  # is this the latest attempt
    
    # Relationship
    question = relationship("Question", back_populates="attempts")

class HintUsage(Base):
    """Track which hints a student has used"""
    __tablename__ = "hint_usage"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    challenge_id = Column(UUID(as_uuid=True), ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    hint_id = Column(UUID(as_uuid=True), ForeignKey("question_hints.id", ondelete="CASCADE"), nullable=False)
    used_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class EditorEvent(Base):
    """Track editor events for plagiarism detection"""
    __tablename__ = "editor_events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    challenge_id = Column(UUID(as_uuid=True), ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(50), nullable=False)  # paste, focus, blur, etc.
    occurred_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    payload_json = Column(JSONB, nullable=True)  # additional event data

class PlagiarismCheck(Base):
    """Store plagiarism check results"""
    __tablename__ = "plagiarism_checks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id = Column(UUID(as_uuid=True), ForeignKey("question_attempts.id", ondelete="CASCADE"), nullable=False)
    similarity_score = Column(Integer, nullable=False)  # percentage
    matched_user_ids = Column(JSONB, nullable=True)  # array of user IDs with similar code
    status = Column(String(50), nullable=False, default="pending")  # pending, flagged, cleared
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)