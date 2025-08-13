"""Pydantic models for authentication."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    """Credentials supplied for user authentication."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Bearer token returned upon successful authentication."""

    access_token: str
    token_type: str = "bearer"
