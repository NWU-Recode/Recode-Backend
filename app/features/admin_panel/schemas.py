from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, List

class EnrolmentBase(BaseModel):
    semester_id: UUID
    student_id: int
    module_id: UUID
    status: Optional[str] = "enrolled"

class EnrolmentCreate(EnrolmentBase):
    pass

class EnrolmentResponse(EnrolmentBase):
    id: UUID
    enrolled_on: datetime

    class Config:
        from_attributes = True

class EnrolmentBatch(BaseModel):
    students: List[int]
    module_id: UUID
    semester_id: UUID
