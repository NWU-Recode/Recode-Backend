"""Authentication API routes (thin wrappers)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .schemas import (
    LoginRequest,
    TokenResponse,
    RegisterRequest,
    PasswordChangeRequest,
    LogoutResponse,
)
from .service import (
    authenticate_user,
    register_user,
    change_password,
    logout_user,
    security,
)
from app.common.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
async def register(data: RegisterRequest) -> TokenResponse:
    return await register_user(data)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest) -> TokenResponse:
    return await authenticate_user(data)


@router.put("/change-password")
async def change_user_password(
    data: PasswordChangeRequest,
    current_user = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    return await change_password(data, current_user, credentials)


@router.post("/logout", response_model=LogoutResponse)
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    return await logout_user(credentials)
