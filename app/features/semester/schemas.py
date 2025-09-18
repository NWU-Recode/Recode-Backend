from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class SemesterBase(BaseModel):
    year: int
    term_name: str
    start_date: datetime
    end_date: datetime
    is_current: bool = False

class SemesterCreate(SemesterBase):
    pass

class SemesterResponse(SemesterBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
