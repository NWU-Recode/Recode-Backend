"""Authentication API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from .schemas import (
    LoginRequest, 
    TokenResponse, 
    RegisterRequest, 
    PasswordChangeRequest,
    LogoutResponse
)
from .service import (
    authenticate_user, 
    register_user, 
    change_password, 
    logout_user
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
async def register(data: RegisterRequest) -> TokenResponse:
    """Register a new user account."""
    return await register_user(data)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest) -> TokenResponse:
    """Authenticate a user and return an access token."""
    return await authenticate_user(data)


@router.put("/change-password")
async def change_user_password(data: PasswordChangeRequest, current_user = Depends(change_password)):
    """Change user password."""
    return current_user


@router.post("/logout", response_model=LogoutResponse)
async def logout():
    """Logout user (token invalidation handled by Supabase)."""
    return await logout_user()
