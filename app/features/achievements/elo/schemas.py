from pydantic import BaseModel
from datetime import datetime

class EloHistorySchema(BaseModel):
    id: int
    user_id: int
    elo_score: int
    change_reason: str
    created_at: datetime

    class Config:
        from_attributes = True
