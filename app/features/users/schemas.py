"""Pydantic models for user resources."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from typing import Optional, Dict, Any

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    """Base user fields."""
    email: EmailStr
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str


class UserUpdate(BaseModel):
    """Schema for updating user profile."""
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None


class UserRoleUpdate(BaseModel):
    """Schema for updating user role (admin only)."""
    role: str


class User(BaseModel):
    """Represents a user stored in the database."""
    id: UUID
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


class UserProfile(BaseModel):
    """User profile for public viewing."""
    id: UUID
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    role: str
    created_at: datetime

    class Config:
        from_attributes = True
