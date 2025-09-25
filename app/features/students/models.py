from typing import List, Optional
from pydantic import BaseModel, EmailStr

# For GET /student/me
class StudentProfile(BaseModel):
    id: int
    email: EmailStr
    first_name: str
    last_name: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None

# For PATCH /student/me
class StudentProfileUpdate(BaseModel):
    email: Optional[EmailStr]
    full_name: Optional[str]
    avatar_url: Optional[str]
    phone: Optional[str]
    bio: Optional[str]

# For GET /student/me/modules
class ModuleProgress(BaseModel):
    module_id: str
    module_code: str
    module_name: str
    progress_percent: float

# For GET /student/me/badges
class BadgeInfo(BaseModel):
    badge_id: str
    name: str
    tier: str
    awarded_at: Optional[str]

# For GET /student/me/progress
class StudentProgress(BaseModel):
    total_questions_passed: int
    challenges_completed: int
    elo: int
