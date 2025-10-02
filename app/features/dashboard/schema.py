from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from uuid import UUID
from datetime import date, datetime

class StudentDashboardOut(BaseModel):
    student_id: int
    full_name: str
    avatar_url: Optional[str]
    current_elo: Optional[int]
    current_streak: Optional[int]
    longest_streak: Optional[int]
    active_title: Optional[str]
    enrolled_modules: List[str] = []
    total_badges: int
    correct_submissions: int
    unique_questions_attempted: int
    challenges_completed: int
    last_submission: Optional[str]

class CurrentWeekResponse(BaseModel):
    current_week: int
    
    class Config:
        from_attributes = True