from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
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
    max_score: int = Field(..., example=100)


class ChallengeCreate(ChallengeBase):
    pass


class ChallengeUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    max_score: Optional[int] = None
    is_active: Optional[bool] = None


class ChallengeResponse(ChallengeBase):
    id: UUID
    module_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ===========================
# STUDENT SCHEMAS
# ===========================
class StudentResponse(BaseModel):
    id: int
    full_name: str
    email: str

    class Config:
        from_attributes = True
