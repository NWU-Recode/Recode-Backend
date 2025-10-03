from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.features.submissions.schemas import ChallengeQuestionResultSchema
from app.features.achievements.schemas import CheckAchievementsResponse


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


class ChallengeSubmissionOutput(BaseModel):
    question_id: UUID
    output: str
    stdin: Optional[str] = None


class ChallengeSubmitRequest(BaseModel):
    challenge_id: UUID
    items: Optional[List[ChallengeSubmissionOutput]] = None


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
    achievements: Optional[CheckAchievementsResponse] = None


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


class ChallengeQuestionSummary(BaseModel):
    id: UUID
    question_number: Optional[int] = None
    sub_number: Optional[int] = None
    position: Optional[int] = None
    prompt: Optional[str] = None


class ChallengeSummaryItem(BaseModel):
    id: UUID
    title: str
    slug: Optional[str] = None
    module_code: Optional[str] = None
    semester_id: Optional[UUID] = None
    week_number: Optional[int] = None
    status: str
    tier: Optional[str] = None
    challenge_type: Optional[str] = None
    question_count: int
    questions: Optional[List[ChallengeQuestionSummary]] = None


class ChallengeListResponse(BaseModel):
    items: List[ChallengeSummaryItem] = Field(default_factory=list)
    next_cursor: Optional[str] = None
    available_statuses: List[str] = Field(default_factory=list)


class ChallengeDetailResponse(ChallengeSummaryItem):
    description: Optional[str] = None
    release_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    trigger_event: Optional[dict] = None


class QuestionSummary(BaseModel):
    id: UUID
    challenge_id: UUID
    question_number: Optional[int] = None
    sub_number: Optional[int] = None
    position: Optional[int] = None
    prompt: Optional[str] = None


class QuestionTestCase(BaseModel):
    id: UUID
    stdin: Optional[str] = None
    expected_output: Optional[str] = None
    visibility: Optional[str] = None
    order: Optional[int] = None


class QuestionDetail(QuestionSummary):
    question_text: Optional[str] = None
    starter_code: Optional[str] = None
    reference_solution: Optional[str] = None
    language_id: Optional[int] = None
    tier: Optional[str] = None
    difficulty: Optional[str] = None
    samples: Optional[List[dict]] = None
    hints: Optional[List[str]] = None
    testcases: Optional[List[QuestionTestCase]] = None


class ChallengeWithQuestionsResponse(BaseModel):
    challenge: ChallengeDetailResponse
    questions: List[QuestionDetail] = Field(default_factory=list)


class QuestionListResponse(BaseModel):
    items: List[QuestionDetail] = Field(default_factory=list)


class QuestionDetailResponse(QuestionDetail):
    pass


class QuestionTestCaseListResponse(BaseModel):
    items: List[QuestionTestCase] = Field(default_factory=list)
