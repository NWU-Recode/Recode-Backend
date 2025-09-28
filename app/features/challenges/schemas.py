from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.features.submissions.schemas import ChallengeQuestionResultSchema


class Challenge(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    created_at: datetime


class ChallengeAttempt(BaseModel):
    id: UUID
    challenge_id: UUID
    user_id: UUID
    started_at: datetime
    submitted_at: Optional[datetime] = None
    score: int = 0
    correct_count: int = 0
    status: str


class ChallengeMissingCode(BaseModel):
    question_id: UUID
    source_code: str
    stdin: Optional[str] = None


class ChallengeSubmitRequest(BaseModel):
    challenge_id: UUID
    items: Optional[List[ChallengeMissingCode]] = None


class ChallengeSubmitResponse(BaseModel):
    challenge_attempt_id: UUID
    challenge_id: UUID
    status: str
    gpa_score: int
    gpa_max_score: int
    elo_delta: int
    base_elo_total: int
    efficiency_bonus_total: int
    tests_total: int
    tests_passed_total: int
    time_used_seconds: Optional[int] = None
    time_limit_seconds: Optional[int] = None
    average_execution_time_ms: Optional[float] = None
    average_memory_used_kb: Optional[float] = None
    badge_tiers_awarded: List[str] = Field(default_factory=list)
    passed_question_ids: List[UUID]
    failed_question_ids: List[UUID]
    missing_question_ids: List[UUID]
    question_results: List[ChallengeQuestionResultSchema]


class ChallengeAttemptQuestionStatus(BaseModel):
    question_id: UUID
    status: str
    last_submitted_at: Optional[datetime] = None
    token: Optional[str] = None


class GetChallengeAttemptResponse(BaseModel):
    challenge_attempt_id: UUID
    challenge_id: UUID
    status: str
    started_at: Optional[datetime] = None
    deadline_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    snapshot_question_ids: List[UUID]
    questions: List[ChallengeAttemptQuestionStatus]


class ChallengeSchema(BaseModel):
    id: int
    name: str
    description: Optional[str]
    kind: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChallengeGenerateRequest(BaseModel):
    module_code: Optional[str] = None
    week_number: int
    
    class Config:
        extra = "forbid"


class WeekSchema(BaseModel):
    start_date: datetime
    end_date: datetime
