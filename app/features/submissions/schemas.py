from __future__ import annotations

<<<<<<< HEAD
from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, Field

from app.features.submissions.comparison import ComparisonMode


class QuestionTestSchema(BaseModel):
    id: Optional[str] = None
    question_id: str
    input: str
    expected: str
    visibility: Optional[str] = None
    order_index: int
    expected_hash: Optional[str] = None
    compare_mode: str = ComparisonMode.AUTO
    compare_config: Dict[str, Any] = Field(default_factory=dict)


=======
from typing import Dict, List, Optional, Literal

from pydantic import BaseModel, Field

>>>>>>> acf079eb3553ddd1e34eea9f50ab734671512fe4
class QuestionBundleSchema(BaseModel):
    challenge_id: str
    question_id: str
    title: str
    prompt: str
    starter_code: str
    reference_solution: Optional[str] = None
    expected_output: Optional[str] = None
    tier: Optional[str] = None
    language_id: int
    points: int
    max_time_ms: Optional[int] = None
    max_memory_kb: Optional[int] = None
    badge_id: Optional[str] = None


class TestRunResultSchema(BaseModel):
<<<<<<< HEAD
    test_id: Optional[str] = None
    visibility: Optional[str] = None
=======
    test_id: str = Field(default="expected_output")
    visibility: Literal["public"] = Field(default="public")
>>>>>>> acf079eb3553ddd1e34eea9f50ab734671512fe4
    passed: bool
    stdout: Optional[str] = None
    expected_output: Optional[str] = None
    status_id: int = Field(default=3)
    status_description: Literal["accepted", "mismatch"] = Field(default="accepted")
    detail: Optional[str] = None
    score_awarded: int = 0
    gpa_contribution: int = 0
    compare_mode_applied: Optional[str] = None
    normalisations_applied: Optional[List[str]] = None
    why_failed: Optional[str] = None
    comparison_attempts: Optional[List[Dict[str, Any]]] = None


class QuestionEvaluationRequest(BaseModel):
<<<<<<< HEAD
    source_code: str
=======
    output: str
    language_id: Optional[int] = None
>>>>>>> acf079eb3553ddd1e34eea9f50ab734671512fe4


class QuestionSubmissionRequest(QuestionEvaluationRequest):
    include_private: bool = True


class BatchSubmissionEntry(BaseModel):
    output: str

    @classmethod
    def validate_entry(cls, value: Dict[str, object]) -> "BatchSubmissionEntry":
        if not isinstance(value, dict):
            raise ValueError("submission entry must be an object with an output string")
        if "output" not in value or not isinstance(value.get("output"), str):
            raise ValueError("submission entry output must be provided as string")
        return cls(output=value["output"])  # type: ignore[arg-type]


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
    submission_id: Optional[str] = None
    attempt_id: Optional[str] = None
    attempt_number: Optional[int] = None
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

