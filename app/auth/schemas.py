"""Pydantic models for authentication."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    """Credentials supplied for user authentication."""

    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr
    password: str
    full_name: str


class TokenResponse(BaseModel):
    """Bearer token returned upon successful authentication."""

    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    role: str


class PasswordChangeRequest(BaseModel):
    """Request to change password."""
    current_password: str
    new_password: str


class LogoutResponse(BaseModel):
    """Response after logout."""
    message: str = "Logged out successfully"
