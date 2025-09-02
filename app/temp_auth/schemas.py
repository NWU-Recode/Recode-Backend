from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = None

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
