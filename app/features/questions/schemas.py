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
