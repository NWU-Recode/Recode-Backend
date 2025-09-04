from __future__ import annotations
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class Challenge(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    difficulty: str
    topic: str
    week_number: Optional[int] = None
    challenge_type: str  # "weekly" or "special"
    created_at: datetime

class ChallengeCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    difficulty: str
    topic: str
    week_number: Optional[int] = None
    challenge_type: str = "weekly"

class WeeklyCreateRequest(BaseModel):
    week_number: int
    slides_url: str
    force: bool = False

class SpecialCreateRequest(BaseModel):
    difficulty: str  # "ruby", "emerald", "diamond"
    topic: Optional[str] = None

