from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator

from app.features.submissions.comparison import ComparisonMode


class QuestionTestSchema(BaseModel):
	id: Optional[str] = None
	question_id: str
	input: str
	expected: str
	visibility: Optional[str] = None
	order_index: int = 0
	expected_hash: Optional[str] = None
	compare_mode: str = ComparisonMode.AUTO
	compare_config: Dict[str, Any] = Field(default_factory=dict)


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
	tests: List[QuestionTestSchema] = Field(default_factory=list)


class TestRunResultSchema(BaseModel):
	test_id: Optional[str] = None
	visibility: Optional[str] = None
	passed: bool
	stdout: str = ""  # Changed from Optional[str] = None to always include in response
	expected_output: Optional[str] = None
	stderr: Optional[str] = None
	compile_output: Optional[str] = None
	status_id: Optional[int] = 3
	status_description: Optional[str] = None
	detail: Optional[str] = None
	score_awarded: int = 0
	gpa_contribution: int = 0
	token: Optional[str] = None
	execution_time: Optional[str] = None
	execution_time_seconds: Optional[float] = None
	execution_time_ms: Optional[float] = None
	memory_used: Optional[int] = None
	memory_used_kb: Optional[int] = None
	compare_mode_applied: Optional[str] = None
	normalisations_applied: Optional[List[str]] = None
	why_failed: Optional[str] = None
	# comparison_attempts removed - internal debugging info not needed in API response


class QuestionEvaluationRequest(BaseModel):
	output: Optional[str] = None
	source_code: Optional[str] = None
	language_id: Optional[int] = None

	@model_validator(mode="after")
	def ensure_payload(cls, model: "QuestionEvaluationRequest") -> "QuestionEvaluationRequest":
		if model.output is None and model.source_code is None:
			raise ValueError("request must include either output or source_code")
		return model


class QuestionSubmissionRequest(BaseModel):
	source_code: str
	language_id: Optional[int] = None
	include_private: bool = True

	@model_validator(mode="after")
	def ensure_payload(cls, model: "QuestionSubmissionRequest") -> "QuestionSubmissionRequest":
		if not model.source_code or not model.source_code.strip():
			raise ValueError("source_code is required for submission")
		return model


class BatchSubmissionEntry(BaseModel):
	source_code: str
	language_id: Optional[int] = None

	@model_validator(mode="after")
	def ensure_payload(cls, model: "BatchSubmissionEntry") -> "BatchSubmissionEntry":
		if not model.source_code or not model.source_code.strip():
			raise ValueError("submission entry must include source_code")
		return model

	@classmethod
	def validate_entry(cls, value: Dict[str, Any]) -> "BatchSubmissionEntry":
		if not isinstance(value, dict):
			raise ValueError("submission entry must be an object with grading data")
		return cls(**value)


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



