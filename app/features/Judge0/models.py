from sqlalchemy import Column, String, Text, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
import uuid

class CodeSubmission(Base):
    """Code submissions table"""
    __tablename__ = "code_submissions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_code = Column(Text, nullable=False)
    language_id = Column(Integer, nullable=False)
    stdin = Column(Text, nullable=True)
    expected_output = Column(Text, nullable=True)
    judge0_token = Column(String(255), unique=True, nullable=True, index=True)
    status = Column(String(50), default="pending", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    results = relationship("CodeResult", back_populates="submission", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<CodeSubmission(id={self.id}, status={self.status})>"

class CodeResult(Base):
    """Code execution results table"""
    __tablename__ = "code_results"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id = Column(UUID(as_uuid=True), ForeignKey("code_submissions.id", ondelete="CASCADE"), nullable=False, index=True)
    stdout = Column(Text, nullable=True)
    stderr = Column(Text, nullable=True)
    compile_output = Column(Text, nullable=True)
    execution_time = Column(String(50), nullable=True)
    memory_used = Column(Integer, nullable=True)  # in KB
    status_id = Column(Integer, nullable=False)
    status_description = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    submission = relationship("CodeSubmission", back_populates="results")
    
    def __repr__(self):
        return f"<CodeResult(id={self.id}, status_id={self.status_id})>"
