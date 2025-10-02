from pydantic import BaseModel,computed_field, Field
from typing import List, Optional, Dict
from uuid import UUID

# ------------------- Student -------------------


class StudentChallengeFeedbackOut(BaseModel):
    student_id: int
    challenge_id: UUID
    challenge_name: str
    challenge_type: str
    week_number: Optional[int]
    module_code: str
    module_name: str
    total_questions: int
    questions_correct: int
    challenge_completion_rate: float

# ------------------- Badges -------------------
class BadgeSummaryOut(BaseModel):
    badge_type: str
    badge_count: int
    latest_award: Optional[str]

# ------------------- Challenges -------------------
class ChallengeProgressOut(BaseModel):
    challenge_id: Optional[UUID]
    challenge_name: Optional[str]
    challenge_type: Optional[str]
    week_number: Optional[int]=None
    challenge_tier: Optional[str]
    module_code: Optional[str]
    total_enrolled_students: Optional[int]
    students_completed: Optional[int]
    total_question_attempts: Optional[int]
    challenge_participation_rate: Optional[float]
    challenge_completion_rate: Optional[float]
    difficulty_breakdown: Optional[Dict[str, int]]
    avg_elo_of_successful_students: Optional[float]
    avg_completion_time_minutes: Optional[float]

# ------------------- Modules -------------------
class ModuleOverviewOut(BaseModel):
    module_code: str
    module_name: str
    total_enrolled_students: int
    total_challenges: int
class AdminModuleOverviewOut(BaseModel):
    code: str = Field(..., example="CS101")
    name: str = Field(..., example="Introduction to Programming")
    description: Optional[str] = Field(None, example="Learn the basics of programming")
    semester_id: UUID = Field(..., example="d290f1ee-6c54-4b01-90e6-d701748f0851")
    lecturer_id: Optional[int] = Field(..., example=12345)
    code_language: Optional[str] = Field(None, example="Python")
    credits: Optional[int] = Field(None, example=12)

# ------------------- Leaderboards -------------------
class ModuleLeaderboardOut(BaseModel):
    module_id: UUID
    module_code: str
    module_name: str
    student_id: int
    full_name: str
    avatar_url: Optional[str]
    current_elo: Optional[int]
    total_badges: int
    rank_in_module: int

class GlobalLeaderboardOut(BaseModel):
    student_id: int
    full_name: str
    current_elo: Optional[int]
    total_badges: int
    global_rank: int

# ------------------- Lecturer -------------------
class HighRiskStudentOut(BaseModel):
    student_id: int
    full_name: str
    module_code: str
    total_enrolled_modules: int
    challenges_completed: int
    completion_rate: Optional[float]
    current_elo: Optional[int]
    high_risk: bool

class QuestionProgressOut(BaseModel): 
    question_number: int
    question_type: Optional[str]
    challenge_name: str
    challenge_tier: Optional[str]
    module_code: str
    students_attempted: int
    total_submissions: int
    correct_submissions: int
    success_rate: Optional[float]
    avg_elo_earned: Optional[float]
    avg_completion_time_minutes: Optional[float]

class ChallengeProgressResponse(BaseModel):
    student_number: int
    student_name: str
    challenge_name: str
    highest_badge: str  # bronze, silver, gold, ruby, emerald, diamond, or none
    total_time_ms: int  # Sum of (finished_at - created_at) for all submissions
    total_submissions: int  # Number of code submissions
    
    @computed_field
    @property
    def total_time(self) -> str:
        """Format time as HH:MM:SS"""
        seconds = int(self.total_time_ms // 1000)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    class Config:
        from_attributes = True