from __future__ import annotations
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel

class SubmissionCreate(BaseModel):
    source_code: str
    language_id: int
    stdin: Optional[str] = None
    expected_output: Optional[str] = None
    question_id: Optional[str] = None  # UUID string; optional join to question

class SubmissionRecord(BaseModel):
    id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    source_code: str
    language_id: int
    stdin: Optional[str] = None
    expected_output: Optional[str] = None
    judge0_token: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class SubmissionWithResults(BaseModel):
    submission: Dict[str, Any]
    results: List[Dict[str, Any]]

class SubmissionResultCreate(BaseModel):
    submission_id: str
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    compile_output: Optional[str] = None
    execution_time: Optional[str] = None
    memory_used: Optional[int] = None
    status_id: int
    status_description: str
    language_id: int

class LanguageStat(BaseModel):
    language_id: int
    submission_count: int

class SubmissionStatusUpdate(BaseModel):
    """Update submission status"""
    status: str
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

class BatchSubmissionRequest(BaseModel):
    """Batch submission processing request"""
    submission_tokens: List[str]
    priority: int = 0

class BatchSubmissionResponse(BaseModel):
    """Response for batch submission processing"""
    processed_count: int
    failed_count: int
    results: List[Dict[str, Any]]

class SubmissionStatsResponse(BaseModel):
    """Comprehensive submission statistics"""
    user_id: str
    total_submissions: int
    total_attempts: int
    correct_attempts: int
    accuracy_rate: float
    language_distribution: Dict[str, int]
    status_distribution: Dict[str, int]
    average_execution_time: Optional[str]
    total_memory_used: Optional[int]

class SubmissionTimelineItem(BaseModel):
    """Timeline item for submission history"""
    submission_id: str
    question_id: Optional[str]
    language_id: int
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    execution_time: Optional[str]
    memory_used: Optional[int]
    success: Optional[bool]

class SubmissionTimelineResponse(BaseModel):
    """Timeline of submissions"""
    timeline: List[SubmissionTimelineItem]
    total_count: int

class PendingSubmissionResponse(BaseModel):
    """Response for pending submission check"""
    submission_id: str
    judge0_token: str
    status: str
    estimated_completion: Optional[datetime]

class ResubmissionRequest(BaseModel):
    """Request to resubmit failed submissions"""
    user_id: Optional[str] = None
    submission_ids: Optional[List[str]] = None
    max_age_hours: int = 24

class ResubmissionResponse(BaseModel):
    """Response for resubmission operation"""
    resubmitted_count: int
    failed_count: int
    results: List[Dict[str, Any]]

class SubmissionCleanupRequest(BaseModel):
    """Request to cleanup old submissions"""
    days_old: int = 30
    status_filter: Optional[str] = "completed"
    dry_run: bool = False

class SubmissionCleanupResponse(BaseModel):
    """Response for cleanup operation"""
    deleted_count: int
    freed_space_mb: Optional[float]
    dry_run: bool

# CHALLENGE ATTEMPT SCHEMAS

class ChallengeAttemptCreate(BaseModel):
    """Create new challenge attempt"""
    challenge_id: str
    user_id: str
    deadline_at: Optional[datetime]

class ChallengeAttemptResponse(BaseModel):
    """Challenge attempt information"""
    id: str
    challenge_id: str
    user_id: str
    status: str
    score: int
    total_correct: int
    total_questions: int
    started_at: datetime
    submitted_at: Optional[datetime]
    deadline_at: Optional[datetime]
    time_taken_seconds: Optional[int]
    hints_used_total: int

class ChallengeAttemptSummary(BaseModel):
    """Summary of challenge attempt"""
    attempt_id: str
    challenge_title: str
    status: str
    score: int
    completion_percentage: float
    started_at: datetime
    time_taken_seconds: Optional[int]

class ChallengeProgressResponse(BaseModel):
    """Progress tracking for challenge"""
    challenge_id: str
    user_id: str
    total_questions: int
    completed_questions: int
    correct_answers: int
    progress_percentage: float
    estimated_time_remaining: Optional[int]
    hints_available: int
    hints_used: int

# QUEUE MANAGEMENT SCHEMAS

class SubmissionQueueItem(BaseModel):
    """Queue item for async processing"""
    id: str
    user_id: str
    question_id: str
    judge0_token: str
    priority: int
    status: str
    created_at: datetime
    retry_count: int

class QueueStatusResponse(BaseModel):
    """Queue status information"""
    total_pending: int
    total_processing: int
    total_failed: int
    average_wait_time_seconds: Optional[float]
    estimated_completion_time: Optional[datetime]