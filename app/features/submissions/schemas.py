from __future__ import annotations

from typing import List, Optional, Literal

from pydantic import BaseModel, Field


class QuestionTestSchema(BaseModel):
    """Representation of a single stored test case for a question."""

    id: Optional[str] = None
    question_id: str
    input: str
    expected: str
    visibility: Literal["public", "private"]
    order_index: int


class QuestionBundleSchema(BaseModel):
    """Full payload returned to the frontend for a question + its tests."""

    challenge_id: str
    question_id: str
    title: str
    prompt: str
    starter_code: str
    reference_solution: Optional[str] = None
    tier: Optional[str] = None
    language_id: int
    points: int
    tests: List[QuestionTestSchema]


class TestRunResultSchema(BaseModel):
    """Result of executing a single Judge0-backed test."""

    test_id: Optional[str] = None
    visibility: Literal["public", "private"]
    passed: bool
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    status_id: int
    status_description: str
    token: Optional[str] = None
    execution_time: Optional[str] = None
    memory_used: Optional[int] = None


class QuestionEvaluationRequest(BaseModel):
    """User supplied code to evaluate against a question's tests."""

    source_code: str
    language_id: Optional[int] = None


class QuestionEvaluationResponse(BaseModel):
    """Aggregated grading outcome for a question."""

    challenge_id: str
    question_id: str
    tier: Optional[str] = None
    language_id: int
    gpa_weight: int
    gpa_awarded: int
    elo_awarded: int
    public_passed: bool
    tests: List[TestRunResultSchema]


class ChallengeQuestionResultSchema(QuestionEvaluationResponse):
    """Extends evaluation response with submission metadata for challenge grading."""

    pass


class ChallengeSubmissionBreakdown(BaseModel):
    """High level grading aggregates for a challenge submission."""

    challenge_id: str
    attempt_id: str
    gpa_score: int
    gpa_max_score: int
    elo_delta: int
    passed_questions: List[str] = Field(default_factory=list)
    failed_questions: List[str] = Field(default_factory=list)
    missing_questions: List[str] = Field(default_factory=list)
    question_results: List[ChallengeQuestionResultSchema] = Field(default_factory=list)

