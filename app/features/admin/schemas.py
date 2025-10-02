from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime, date
from typing import Optional


# ===========================
# MODULE SCHEMAS
# ===========================
class ModuleBase(BaseModel):
    code: str = Field(..., example="CS101")
    name: str = Field(..., example="Introduction to Programming")
    description: Optional[str] = Field(None, example="Learn the basics of programming")
    semester_id: UUID = Field(..., example="d290f1ee-6c54-4b01-90e6-d701748f0851")
    lecturer_id: int = Field(..., example=12345)
    code_language: Optional[str] = Field(None, example="Python")
    credits: Optional[int] = Field(None, example=12)


class ModuleCreate(ModuleBase):
    pass


class ModuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    code_language: Optional[str] = None
    credits: Optional[int] = None


class ModuleResponse(ModuleBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # works like orm_mode


# ===========================
# CHALLENGE SCHEMAS
# ===========================
class ChallengeBase(BaseModel):
    title: str = Field(..., example="Final Project")
    description: Optional[str] = Field(None, example="Build a small app")
    challenge_type: str = Field(..., example="weekly") 


class ChallengeCreate(ChallengeBase):
    pass


class ChallengeUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    max_score: Optional[int] = None
    is_active: Optional[bool] = None



class ChallengeResponse(ChallengeBase):
    id: UUID
    module_code: str
    challenge_type: str
    title: str
    description: Optional[str] = None
    status: Optional[str] = None
    release_date: datetime
    due_date: datetime
    created_at: datetime
    updated_at: datetime
    
    # Conditional fields based on challenge_type
    week_number: Optional[int] = None  # Only for weekly challenges
    tier: Optional[str] = None  # Only for special challenges
    trigger_event: Optional[dict] = None  # Only for special challenges (jsonb)

    class Config:
        from_attributes = True


# ===========================
# STUDENT SCHEMAS
# ===========================
class StudentResponse(BaseModel):
    student_number: int

    class Config:
        from_attributes = True


# ===========================
# ENROLMENT / ADMIN SCHEMAS
# ===========================

class EnrolRequest(BaseModel):
    student_number: int
    semester_id: Optional[UUID] = None
    status: Optional[str] = "active"


class BatchEnrolRequest(BaseModel):
    student_numbers: list[int]
    semester_id: Optional[UUID] = None


class AssignLecturerRequestByBody(BaseModel):
    lecturer_id: int
    module_code: Optional[str] = None
    #module_id: Optional[UUID] = None

class AssignLecturerRequest(BaseModel):
    lecturer_id: int

class RemoveLecturerRequest(BaseModel):
    module_code: Optional[str] = None
    #module_id: Optional[UUID] = None

"""
class SemesterCreate(BaseModel):
    year: int
    term_name: Optional[str] = "Semester 1"
    start_date: date
    end_date: date
    is_current: Optional[bool] = False
""" 

class ModuleAdminCreate(BaseModel):
    code: str
    name: str
    description: str
    semester_id: Optional[UUID] = None
    lecturer_id: int
    code_language: Optional[str] = None
    credits: Optional[int] = 8

# ===========================
# LECTURER PROFILE SCHEMAS
# ===========================
class LecturerProfileResponse(BaseModel):
    id: int
    email: str
    full_name: str
    avatar_url: Optional[str]
    phone: Optional[str]
    bio: Optional[str]
