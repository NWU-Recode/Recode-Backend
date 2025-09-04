from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = None
    student_number: Optional[int] = Field(
        default=None,
        ge=10000000,
        le=99999999,
        description="Optional 8-digit student number (if supplied, stored in auth user metadata and used by DB trigger as profile id)",
    )

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: Optional[int] = None  # seconds (from Supabase)

class ProfileOut(BaseModel):
    id: str
    email: EmailStr
    role: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None

