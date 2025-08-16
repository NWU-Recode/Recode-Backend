"""Authentication service functions (Supabase Auth wrapper)."""

from __future__ import annotations

from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.DB.supabase import get_supabase
from app.Auth.schemas import LoginRequest, TokenResponse, RegisterRequest, PasswordChangeRequest
from app.features.users.service import (
    ensure_user_provisioned,
    update_user_last_signin,
)

security = HTTPBearer()


async def register_user(data: RegisterRequest) -> TokenResponse:
    """Register a new user with Supabase Auth then ensure local profile row (idempotent)."""
    client = await get_supabase()
    try:
        auth_response = await client.auth.sign_up({
            "email": data.email,
            "password": data.password,
        })
        if not auth_response.user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to create user account")

        # Sign in to obtain session (some providers auto sign-in)
        signin_response = await client.auth.sign_in_with_password({
            "email": data.email,
            "password": data.password,
        })
        if not signin_response.session:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to sign in after registration")

        db_user = await ensure_user_provisioned(auth_response.user.id, data.email, data.full_name)

        return TokenResponse(
            access_token=signin_response.session.access_token,
            user_id=str(db_user.get("id")),
            email=db_user.get("email"),
            role=db_user.get("role"),
        )
    except Exception as exc:  # noqa: BLE001
        if "User already registered" in str(exc):  # Supabase specific string
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User with this email already exists")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Registration failed: {exc}") from exc


async def authenticate_user(data: LoginRequest) -> TokenResponse:
    """Authenticate user (email/password) and auto-provision local row (idempotent)."""
    client = await get_supabase()
    try:
        result = await client.auth.sign_in_with_password({"email": data.email, "password": data.password})
        if not result.session or not result.user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authentication failed")

        db_user = await ensure_user_provisioned(result.user.id, result.user.email, (result.user.user_metadata or {}).get("full_name"))
        await update_user_last_signin(db_user.get("id"))  # type: ignore[arg-type]

        return TokenResponse(
            access_token=result.session.access_token,
            user_id=str(db_user.get("id")),
            email=db_user.get("email"),
            role=db_user.get("role"),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authentication failed") from exc

#to be researched
async def change_password(
    data: PasswordChangeRequest,
    current_user,  # injected via route dependency from common.deps.get_current_user
    credentials: HTTPAuthorizationCredentials,
) -> dict:
    """Change user password by re-validating the current password via Supabase."""
    client = await get_supabase()
    email = getattr(current_user, "email", None) or (current_user.get("email") if isinstance(current_user, dict) else None)  # type: ignore[call-arg]
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User email not found")
    try:
        await client.auth.sign_in_with_password({"email": email, "password": data.current_password})
        await client.auth.update_user({"password": data.new_password})
        return {"message": "Password updated successfully"}
    except Exception:  
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to change password")


async def logout_user(credentials: HTTPAuthorizationCredentials) -> dict: 
    #Logout user (token invalidation handled by Supabase automatically).
    return {"message": "Logged out successfully"}
