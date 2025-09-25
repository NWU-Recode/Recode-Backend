from __future__ import annotations

from typing import List, Optional, Literal

from pydantic import BaseModel, Field


class QuestionTestSchema(BaseModel):
    id: Optional[str] = None
    question_id: str
    input: str
    expected: str
    visibility: Literal["public", "private"]
    order_index: int


class QuestionBundleSchema(BaseModel):
    challenge_id: str
    question_id: str
    title: str
    prompt: str
    starter_code: str
    reference_solution: Optional[str] = None
    tier: Optional[str] = None
    language_id: int
    points: int
    max_time_ms: Optional[int] = None
    max_memory_kb: Optional[int] = None
    tests: List[QuestionTestSchema]


class TestRunResultSchema(BaseModel):
    test_id: Optional[str] = None
    visibility: Literal["public", "private"]
    passed: bool
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    status_id: int
    status_description: str
    token: Optional[str] = None
    execution_time: Optional[str] = None
    execution_time_seconds: Optional[float] = None
    execution_time_ms: Optional[float] = None
    memory_used: Optional[int] = None
    memory_used_kb: Optional[int] = None
    score_awarded: int = 0
    gpa_contribution: int = 0


class QuestionEvaluationRequest(BaseModel):
    source_code: str
    language_id: Optional[int] = None


class QuestionEvaluationResponse(BaseModel):
    challenge_id: str
    question_id: str
    tier: Optional[str] = None
    language_id: int
    gpa_weight: int
    gpa_awarded: int
    elo_awarded: int
    elo_base: int
    elo_efficiency_bonus: int
    public_passed: bool
    tests_passed: int
    tests_total: int
    average_execution_time_ms: Optional[float] = None
    average_memory_used_kb: Optional[float] = None
    badge_tier_awarded: Optional[str] = None
    tests: List[TestRunResultSchema]


class ChallengeQuestionResultSchema(QuestionEvaluationResponse):
    pass


class ChallengeSubmissionBreakdown(BaseModel):
    challenge_id: str
    attempt_id: str
    gpa_score: int
    gpa_max_score: int
    elo_delta: int
    base_elo_total: int
    efficiency_bonus_total: int
    tests_total: int
    tests_passed_total: int
    average_execution_time_ms: Optional[float] = None
    average_memory_used_kb: Optional[float] = None
    time_used_seconds: Optional[int] = None
    time_limit_seconds: Optional[int] = None
    passed_questions: List[str] = Field(default_factory=list)
    failed_questions: List[str] = Field(default_factory=list)
    missing_questions: List[str] = Field(default_factory=list)
    badge_tiers_awarded: List[str] = Field(default_factory=list)
    question_results: List[ChallengeQuestionResultSchema] = Field(default_factory=list)
