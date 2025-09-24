from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class BadgeAwardSchema(BaseModel):
    id: int
    user_id: int
    badge_type: str
    awarded_at: datetime

    class Config:
        from_attributes = True

class BadgeInfo(BaseModel):
    id: str
    name: str
    description: Optional[str]
    badge_type: str
    icon_url: Optional[str]
    question_id: str
    awarded_at: Optional[datetime] = None

class BadgeAwardResponse(BaseModel):
    badge_awarded: bool
    badge: Optional[BadgeInfo] = None

class UserBadgesResponse(BaseModel):
    user_id: str
    badges: List[BadgeInfo]
    total_badges: int