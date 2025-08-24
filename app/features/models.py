from sqlalchemy import Column, String, Text, Integer, DateTime, Boolean, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from app.DB.base import Base

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
    compile_output = Column(Text, nullable=True)
    status_id = Column(Integer, nullable=False)
    status_description = Column(String(255), nullable=False)
    time = Column(String(50), nullable=True)  # execution time as string (e.g., "0.001s")
    memory = Column(Integer, nullable=True)  # memory used in KB
    is_correct = Column(Boolean, nullable=True)  # null = not graded yet
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    code_hash = Column(String(64), nullable=True)  # SHA-256 hash for deduplication
    hash = Column(String(64), nullable=True)  # Alternative hash field for compatibility
    idempotency_key = Column(String(100), nullable=True)  # prevent duplicate submissions
    latest = Column(Boolean, nullable=False, default=True)  # is this the latest attempt
    points_awarded = Column(Integer, nullable=False, default=0)  # points earned
    hints_used = Column(Integer, nullable=False, default=0)  # number of hints used
    resubmissions_count = Column(Integer, nullable=False, default=0)  # number of resubmissions
    
    def __repr__(self):
        return f"<QuestionAttempt(id={self.id}, question_id={self.question_id}, user_id={self.user_id})>"

class ChallengeAttempt(Base):
    __tablename__ = "challenge_attempts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    challenge_id = Column(UUID(as_uuid=True), ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), nullable=False, default="in_progress")  # in_progress, submitted, expired
    score = Column(Integer, nullable=False, default=0)
    total_correct = Column(Integer, nullable=False, default=0)
    total_questions = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    deadline_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    snapshot_questions = Column(JSONB, nullable=True)  # snapshot of questions at start time
    time_taken_seconds = Column(Integer, nullable=True)  # total time taken
    hints_used_total = Column(Integer, nullable=False, default=0)  # total hints used across all questions
    
    # Relationship to question attempts
    question_attempts = relationship("QuestionAttempt", back_populates="challenge_attempt")
    
    def __repr__(self):
        return f"<ChallengeAttempt(id={self.id}, challenge_id={self.challenge_id}, user_id={self.user_id})>"

# Add relationship back to QuestionAttempt
QuestionAttempt.challenge_attempt = relationship("ChallengeAttempt", back_populates="question_attempts")

class CodeSubmission(Base):
    """For tracking raw code submissions to Judge0"""
    __tablename__ = "code_submissions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=True)
    source_code = Column(Text, nullable=False)
    language_id = Column(Integer, nullable=False)
    stdin = Column(Text, nullable=True)
    expected_output = Column(Text, nullable=True)
    judge0_token = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False, default="submitted")  # submitted, processing, completed, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

class CodeResult(Base):
    """For storing Judge0 execution results"""
    __tablename__ = "code_results"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id = Column(UUID(as_uuid=True), ForeignKey("code_submissions.id", ondelete="CASCADE"), nullable=False)
    stdout = Column(Text, nullable=True)
    stderr = Column(Text, nullable=True)
    compile_output = Column(Text, nullable=True)
    execution_time = Column(String(50), nullable=True)  # e.g., "0.001"
    memory_used = Column(Integer, nullable=True)  # in KB
    status_id = Column(Integer, nullable=False)
    status_description = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class UserChallengeTimer(Base):
    """Track time spent on challenges"""
    __tablename__ = "user_challenge_timers"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    challenge_id = Column(UUID(as_uuid=True), ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    paused_at = Column(DateTime(timezone=True), nullable=True)
    resumed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)

class SubmissionBatch(Base):
    """For tracking batch submissions"""
    __tablename__ = "submission_batches"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    challenge_id = Column(UUID(as_uuid=True), ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False)
    total_questions = Column(Integer, nullable=False)
    completed_questions = Column(Integer, nullable=False, default=0)
    status = Column(String(50), nullable=False, default="processing")  # processing, completed, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

class SubmissionQueue(Base):
    """Queue for processing submissions asynchronously"""
    __tablename__ = "submission_queue"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    judge0_token = Column(String(255), nullable=False)
    priority = Column(Integer, nullable=False, default=0)  # higher number = higher priority
    status = Column(String(50), nullable=False, default="pending")  # pending, processing, completed, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    error_message = Column(Text, nullable=True)