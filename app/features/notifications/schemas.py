from __future__ import annotations
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class NotificationOut(BaseModel):
    id: str
    user_id: int
    title: Optional[str]
    message: str
    type: Optional[str]
    priority: int = 1
    link_url: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    read: bool = False

    class Config:
        orm_mode = True
