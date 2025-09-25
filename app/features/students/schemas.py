from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, UUID4

# -------------------
# Profile
# -------------------
class StudentProfile(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    avatar_url: Optional[str]
    bio: Optional[str]
    role: str
    is_active: bool
    last_sign_in: Optional[datetime]

# -------------------
# Modules / Dashboard
# -------------------
class ModuleProgress(BaseModel):
    module_id: UUID4
    module_code: str
    module_name: str
    elo: int
    current_title: Optional[str]
    current_streak: int
    longest_streak: int
    total_points: int
    total_questions_passed: int
    challenges_completed: int
    total_badges: int
    last_submission: Optional[datetime]

# -------------------
# Progress & Analytics
# -------------------
class TopicProgress(BaseModel):
    topic_id: UUID4
    topic_title: str
    subtopics: Optional[List[str]]
    mastery: float

class ChallengeProgress(BaseModel):
    challenge_id: UUID4
    challenge_name: str
    tier: str
    passed: int
    total: int
    score: Optional[float]

class StudentProgress(BaseModel):
    profile: StudentProfile
    modules: List[ModuleProgress]
    elo: int
    gpa: Optional[float]
    streak: int
    longest_streak: int
    topics_mastered: List[TopicProgress]
    recent_challenges: List[ChallengeProgress]

# -------------------
# Badges & Achievements
# -------------------
class BadgeInfo(BaseModel):
    id: UUID4
    name: str
    description: Optional[str]
    badge_type: str
    awarded_at: datetime

class StudentAchievements(BaseModel):
    badges: List[BadgeInfo]
    current_title: Optional[str]
