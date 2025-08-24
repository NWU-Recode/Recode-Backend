from __future__ import annotations
from pydantic import BaseModel
from typing import Optional, List, Dict
from uuid import UUID
from datetime import datetime

class Question(BaseModel):
    id: UUID
    challenge_id: UUID
    language_id: int
    expected_output: str
    points: int
    starter_code: Optional[str] = None
    max_time_ms: Optional[int] = None
    max_memory_kb: Optional[int] = None

class ExecuteRequest(BaseModel):
    question_id: UUID
    source_code: str
    stdin: Optional[str] = None

class ExecuteResponse(BaseModel):
    judge0_token: str
    stdout: Optional[str]
    stderr: Optional[str]
    status_id: int
    status_description: str
    is_correct: Optional[bool] = None
    time: Optional[str] = None
    memory: Optional[int] = None

class QuestionSubmitRequest(BaseModel):
    question_id: UUID
    source_code: str
    stdin: Optional[str] = None
    idempotency_key: Optional[str] = None

class QuestionSubmitResponse(BaseModel):
    question_attempt_id: UUID
    challenge_attempt_id: UUID
    token: str
    app_status: str
    is_correct: bool
    stdout: Optional[str]
    stderr: Optional[str]
    status_id: int
    status_description: str
    time: Optional[str] = None
    memory: Optional[int] = None
    points_awarded: int
    hash: Optional[str] = None

class BatchQuestionCode(BaseModel):
    question_id: UUID
    source_code: str
    stdin: Optional[str] = None

class BatchExecuteRequest(BaseModel):
    challenge_id: UUID
    items: List[BatchQuestionCode]

class BatchExecuteItemResponse(BaseModel):
    question_id: UUID
    judge0_token: str
    is_correct: Optional[bool]
    stdout: Optional[str]
    stderr: Optional[str]
    status_id: int
    status_description: str
    time: Optional[str] = None
    memory: Optional[int] = None
    points_awarded: Optional[int] = None

class BatchExecuteResponse(BaseModel):
    items: List[BatchExecuteItemResponse]

class BatchSubmitRequest(BaseModel):
    challenge_id: UUID
    items: List[BatchQuestionCode]

class BatchSubmitItemResponse(BaseModel):
    question_id: UUID
    question_attempt_id: UUID
    token: str
    app_status: str
    is_correct: bool
    stdout: Optional[str]
    stderr: Optional[str]
    status_id: int
    status_description: str
    time: Optional[str] = None
    memory: Optional[int] = None
    points_awarded: int

class BatchSubmitResponse(BaseModel):
    items: List[BatchSubmitItemResponse]

class TileItem(BaseModel):
    question_id: UUID
    status: str  # unattempted | passed | failed
    last_submitted_at: Optional[datetime] = None
    token: Optional[str] = None

class ChallengeTilesResponse(BaseModel):
    challenge_id: UUID
    items: List[TileItem]

class QuestionAttempt(BaseModel):
    id: UUID
    question_id: UUID
    user_id: UUID
    judge0_token: str
    source_code: str
    stdout: Optional[str]
    stderr: Optional[str]
    status_id: int
    status_description: str
    time: Optional[str]
    memory: Optional[int]
    is_correct: bool
    created_at: datetime

#CAITLIN
class FetchedRequest(BaseModel):
    slide_tags: List[str]  #tags extracted from uploaded slides
    tier : str

class FetchedResponse(BaseModel):
    questions: List['QuestionSummaryResponse']

class QuestionCreateRequest(BaseModel):
    language_id: int
    expected_output: Optional[str]
    points: int
    starter_code: Optional[str]
    max_time_ms: Optional[int]
    max_memory_kb: Optional[int]
    tier: str

class QuestionCreateResponse(BaseModel):
    question_id: str
    message: str = "Question created successfully"
class QuestionUpdateRequest(BaseModel):
    language_id: Optional[int]
    expected_output: Optional[str]
    points: Optional[int]
    starter_code: Optional[str]
    max_time_ms: Optional[int]
    max_memory_kb: Optional[int]
    tier: str

class QuestionUpdateResponse(BaseModel):
    question_id: str
    message: str = "Question updated successfully"

class QuestionSummaryResponse(BaseModel):
    question_id: str
    challenge_id: str
    language_id: int
    points: int
    tier: str


class QuestionStatsResponse(BaseModel):
    total_questions: int            #shows total nr of questions recorded on system
    questions_per_tier: Dict[str, int]     #dictionary that maps tier to questions to get count of each
    questions_per_topic: Dict[str, int] #maps topics to counts
    usage_history: Optional[Dict[str, int]] = {}  #maps question IDs to nr of attempts

class QuestionHintRequest(BaseModel):
    question_id: str
    tier: Optional[str]

class QuestionHintResponse(BaseModel):
    hint_id: str
    question_id: str
    text: str
    

class QuestionHintCreateRequest(BaseModel):
    question_id: str
    text: str
    tier: Optional[str]

class QuestionHintCreateResponse(BaseModel):
    question_id: str
    hint_id: str
    text: str
    tier: Optional[str]
    created_at: datetime

class QuestionHintUpdateRequest(BaseModel):
    hint_id:str
    text: str
    tier: Optional[str]
class QuestionHintUpdateResponse(BaseModel):
    hint_id: str
    question_id: str
    text: str
    tier: Optional[str]
    updated_at: datetime

#Kay

class QuestionDetailResponse(BaseModel):
    """Detailed question information"""
    question_id: str
    challenge_id: Optional[str]
    language_id: int
    expected_output: Optional[str]
    points: int
    starter_code: Optional[str]
    max_time_ms: Optional[int]
    max_memory_kb: Optional[int]
    tier: str
    topic: Optional[str]
    question_text: Optional[str]
    is_active: bool
    created_at: datetime
    hints: List[QuestionHintResponse] = []

class QuestionSearchRequest(BaseModel):
    """Search/filter request for questions"""
    query: Optional[str] = None
    topic: Optional[str] = None
    tier: Optional[str] = None
    language_id: Optional[int] = None
    is_active: Optional[bool] = True
    limit: int = 50
    offset: int = 0

class QuestionSearchResponse(BaseModel):
    """Search results for questions"""
    questions: List[QuestionSummaryResponse]
    total_count: int
    has_more: bool

class QuestionUsageStats(BaseModel):
    """Usage statistics for a question"""
    question_id: str
    times_attempted: int
    times_passed: int
    success_rate: float
    average_time: Optional[str]
    most_common_errors: List[str] = []

class HintUnlockRequest(BaseModel):
    """Request to unlock a hint"""
    question_id: str
    challenge_id: str
    hint_tier: str

class HintUnlockResponse(BaseModel):
    """Response when unlocking a hint"""
    hint_id: str
    text: str
    tier: str
    hints_remaining: int
    penalty_applied: bool

# EDITOR EVENT SCHEMAS

class EditorEventCreate(BaseModel):
    """Create editor event for plagiarism detection"""
    user_id: str
    challenge_id: str
    question_id: str
    event_type: str  # paste, focus, blur, keydown, etc.
    payload: Optional[Dict[str, Any]] = None

class EditorEventResponse(BaseModel):
    """Editor event response"""
    event_id: str
    event_type: str
    occurred_at: datetime
    payload: Optional[Dict[str, Any]]

class PlagiarismCheckRequest(BaseModel):
    """Request plagiarism check"""
    submission_id: str
    check_against_user_ids: Optional[List[str]] = None
    similarity_threshold: float = 0.8

class PlagiarismCheckResponse(BaseModel):
    """Plagiarism check results"""
    check_id: str
    submission_id: str
    similarity_score: int
    matched_submissions: List[Dict[str, Any]]
    status: str
    flagged: bool

# IMPORT/EXPORT SCHEMAS

class QuestionImportRequest(BaseModel):
    """Import questions from file"""
    file_format: str  # "json", "csv", "xlsx"
    questions_data: List[Dict[str, Any]]
    overwrite_existing: bool = False

class QuestionExportRequest(BaseModel):
    """Export questions to file"""
    question_ids: Optional[List[str]] = None
    format: str = "json"  # "json", "csv", "xlsx"
    include_attempts: bool = False
    include_hints: bool = True

class BulkOperationResponse(BaseModel):
    """Response for bulk operations"""
    total_processed: int
    successful: int
    failed: int
    errors: List[Dict[str, Any]]
    operation_id: str