from __future__ import annotations
from datetime import datetime
from uuid import UUID
from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr

class ProfileBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None

class ProfileCreate(ProfileBase):
    password: str

from pydantic import BaseModel, EmailStr, validator

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    student_number: Optional[int] = None  # Make student_number optional

    @validator('student_number')
    def validate_student_number(cls, v):
        if v is not None and not (10000000 <= v <= 99999999):
            raise ValueError('Student number must be exactly 8 digits (e.g., 34250115)')
        return v

    class Config:
        orm_mode = True

class ProfileRoleUpdate(BaseModel):
    role: str

class Profile(BaseModel):
    id: int  # Changed from UUID to int for student number
    supabase_id: str
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    role: str
    is_active: bool
    is_superuser: bool
    email_verified: bool
    last_sign_in: Optional[datetime] = None
    user_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PublicProfile(BaseModel):
    id: int  # Changed from UUID to int for student number
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

class UserSchema(BaseModel):
    id: int
    name: str
    email: str
    role: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
