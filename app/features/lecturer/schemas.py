from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel


class StudentProgressResponse(BaseModel):
    id: str
    email: str
    plain_total: int
    plain_correct: int
    plain_pct: float
    ruby_correct: bool
    emerald_correct: bool
    diamond_correct: bool
    blended_pct: float


class StudentProgressListResponse(BaseModel):
    students: List[StudentProgressResponse]


class UploadSlidesResponse(BaseModel):
    upload_id: str
    pages_extracted: int
    concepts_found: int


class GenerateExercisesRequest(BaseModel):
    upload_id: str
    tier: str # plain|ruby|emerald|diamond
    difficulty: str # easy|medium|hard


class ExerciseResponse(BaseModel):
    id: str
    title: str
    prompt: str
    difficulty: str
    tier: str
    status: str


class ClassCreateRequest(BaseModel):
    name: str
    code: Optional[str] = None
    description: Optional[str] = None


class ClassListItem(BaseModel):
    id: str
    name: str
    code: Optional[str] = None


class AssignChallengeRequest(BaseModel):
    class_id: str
    challenge_id: str
    due_at: Optional[str] = None


class FeedbackRequest(BaseModel):
    comment: Optional[str] = None
    override_score: Optional[float] = None


class AnalyticsPoint(BaseModel):
    label: str
    completion_rate: float
    avg_score: float


class AnalyticsResponse(BaseModel):
    class_id: str
    series: List[AnalyticsPoint]