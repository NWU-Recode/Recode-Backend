from __future__ import annotations
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID

#Achievements Schemas - for dashboard
class AchievementsResponse(BaseModel):
    elo: int
    badges: List[BadgeResponse]
    title: Optional[TitleResponse]

#ELO
class EloResponse(BaseModel):
    elo: int

class EloUpdateRequest(BaseModel):
    submission_id : str

#Badges
class BadgeResponse(BaseModel):
    badge_id: UUID
    badge_name: str
    badge_descrip: Optional[str] 
    date_earned: datetime

class BadgeRequest(BaseModel):
    submission_id: str  #So that if submission = new badge, it can use info from submission for badge?

#this is for when user obtains more than 1 badge for 1 submission
class BadgeBatchAddRequest(BaseModel):
    submission_id: str

class BadgeBatchAddResponse(BaseModel):
    badges: List[BadgeResponse]

#for json schema for badge table
class BadgeActionSchema(BaseModel):
    action_type: str  # like "submit challenges"
    count_required: int 
    description: Optional[str] = None
#Titles
class TitleResponse(BaseModel):
    title_id: str
    title: str
    date_awarded: datetime

#elo points = specific title so if after submission, elo surpasses specific nr, title is unlocked
class TitleUpdateRequest(BaseModel):
    submission_id: str 

#Achievements Trigger
class CheckAchievementsRequest(BaseModel):
    submission_id:str

class CheckAchievementsResponse(BaseModel):
    updated_elo: int
    unlocked_badges: Optional[List[BadgeResponse]]
    new_title: Optional[TitleResponse] = None