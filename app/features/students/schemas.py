from pydantic import BaseModel, EmailStr, UUID4
from typing import Optional, List
#from uuid import UUID
from datetime import datetime

# -------------------
# Profile
# -------------------
class StudentProfile(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    title_name: str
    avatar_url: Optional[str]
    bio: Optional[str]
    role: Optional[str]
    is_active: bool
    last_sign_in: Optional[datetime]

class StudentProfileUpdate(BaseModel):
    email: Optional[EmailStr]
    title: UUID4
    full_name: Optional[str]
    avatar_url: Optional[str]
    phone: Optional[str]
    bio: Optional[str]

# -------------------
# Modules / Dashboard
# -------------------
class ModuleProgress(BaseModel):
    module_id: str
    module_code: str
    module_name: str
    progress_percent: Optional[float] = None
    elo: Optional[int] = None
    current_title: Optional[str] = None
    current_streak: Optional[int] = None
    longest_streak: Optional[int] = None
    total_points: Optional[int] = None
    total_questions_passed: Optional[int] = None
    challenges_completed: Optional[int] = None
    total_badges: Optional[int] = None
    last_submission: Optional[datetime] = None

# -------------------
# Badges
# -------------------
class BadgeInfo(BaseModel):
    id: UUID4
    name: str
    description: Optional[str]
    badge_type: str
    awarded_at: datetime

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
