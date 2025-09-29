from pydantic import BaseModel
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
    lecturer_id: Optional[int]
    lecturer_name: Optional[str]
    total_enrolled_students: int
    total_challenges: int

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
