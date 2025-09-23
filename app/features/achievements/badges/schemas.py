from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class BadgeAwardSchema(BaseModel):
    id: int
    user_id: int
    badge_type: str
    awarded_at: datetime

    class Config:
        from_attributes = True
