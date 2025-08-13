"""Authentication service functions."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.integrations.supabase_session import supabase_session, get_client
from app.auth.schemas import LoginRequest, TokenResponse

security = HTTPBearer()


async def authenticate_user(data: LoginRequest) -> TokenResponse:
    """Authenticate ``data`` against Supabase and return a token."""
    client = await get_client()
    try:
        result = await client.auth.sign_in_with_password(
            {"email": data.email, "password": data.password}
        )
    except Exception as exc:  # pragma: no cover - external failure
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentication failed",
        ) from exc
    if not result.session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentication failed",
        )
    return TokenResponse(access_token=result.session.access_token)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Validate the bearer token and return the associated user."""
    async with supabase_session() as client:
        try:
            user = await client.auth.get_user(credentials.credentials)
        except Exception as exc:  # pragma: no cover - external failure
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
            ) from exc
    if not user.user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    return user.user
