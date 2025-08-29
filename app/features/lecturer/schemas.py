from pydantic import BaseModel
from typing import Optional, List

class StudentProgressResponse(BaseModel):
    student_id: str
    email: str
    plain_pct: float
    ruby_correct: int
    emerald_correct: int
    diamond_correct: int
    blended_pct: float

class ChallengeResponse(BaseModel):
    challenge_id: str
    title: str
    description: Optional[str]
    difficulty: str

class ModuleModel(BaseModel):
    module_id: str
    name: str

class AnalyticsResponse(BaseModel):
    module_id: str
    module_name: str
    avg_score: float
    completion_rate: float
