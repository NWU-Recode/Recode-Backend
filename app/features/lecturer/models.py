from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List


class StudentProgress(BaseModel):
    id: str
    email: str
    plain_total: int
    plain_correct: int
    plain_pct: float
    ruby_correct: bool
    emerald_correct: bool
    diamond_correct: bool
    blended_pct: float


class ClassModel(BaseModel):
    id: str
    name: str
    code: Optional[str] = None
    description: Optional[str] = None


class ExerciseDraft(BaseModel):
    id: Optional[str] = None
    title: str
    prompt: str
    difficulty: str = Field(pattern="^(easy|medium|hard)$")
    tier: str = Field(pattern="^(plain|ruby|emerald|diamond)$")
    status: str = Field(default="draft", pattern="^(draft|published)$")


class SubmissionPreview(BaseModel):
    id: str
    user_id: str
    challenge_id: str
    result_status: str
    runtime_ms: Optional[int] = None
    created_at: Optional[str] = None


class FeedbackUpdate(BaseModel):
    comment: Optional[str] = None
    override_score: Optional[float] = None