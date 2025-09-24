from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, List

# --- Enrolment Schemas ---
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

# --- User role management schemas ---
class UserRoleUpdate(BaseModel):
    user_id: int
    new_role: str

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    role: str
