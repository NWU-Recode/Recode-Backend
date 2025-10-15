#app\features\notifications\schemas.py
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID

class NotificationCreate(BaseModel):
    student_id: int
    challenge_id: UUID
    module_id: UUID
    title: str
    message: str
    link_url: Optional[str] = None

class NotificationOut(BaseModel):
    id: UUID
    student_id: int
    challenge_id: UUID
    module_id: UUID
    title: str
    message: str
    link_url: Optional[str]
    created_at: datetime
    sent: bool = Field(default=False)
