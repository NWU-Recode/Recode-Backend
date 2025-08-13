"""Authentication API routes."""

from __future__ import annotations

from fastapi import APIRouter

from .schemas import LoginRequest, TokenResponse
from .service import authenticate_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest) -> TokenResponse:
    """Authenticate a user and return an access token."""
    return await authenticate_user(data)
