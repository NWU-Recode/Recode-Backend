from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

class User(BaseModel):
    id: UUID
    email: str
    created_at: datetime
    # add more fields to match your Supabase 'users' table

    class Config:
        from_attributes = True  # Pydantic v2