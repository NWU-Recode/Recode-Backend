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
    student_number: int | None = None  # Provided at separate step; required for creation

from pydantic import BaseModel, EmailStr, validator

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None

    class Config:
        from_attributes = True

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
    title_name: Optional[str] = None
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
        from_attributes = True
