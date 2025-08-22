"""Shared FastAPI dependencies for authn/authz & request context."""

from __future__ import annotations

import logging
from uuid import UUID
from functools import lru_cache
from typing import Callable, Iterable, Optional, Any

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr

from app.DB.supabase import get_supabase
from app.features.profiles.service import ensure_profile_provisioned as ensure_user_provisioned, get_profile_by_supabase_id
from app.Auth.deps import get_current_claims
from app.Auth.service import refresh_tokens_if_needed, set_auth_cookies, ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME

logger = logging.getLogger("auth.deps")
security = HTTPBearer(auto_error=True)


class CurrentUser(BaseModel):
    """Minimal user identity shared across endpoints."""
    id: UUID
    email: EmailStr
    role: str


@lru_cache()
def _admin_roles() -> set[str]:  # future extensibility
    return {"admin", "superadmin"}


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> CurrentUser:
    """Resolve and return the current authenticated user (idempotent provisioning).

    Steps:
      1. Validate bearer token via Supabase Auth
      2. Ensure matching row in local users table (auto-provision / reconcile)
      3. Return typed minimal identity object
      4. Log request with X-Request-Id if provided
    """
    client = await get_supabase()
    token = credentials.credentials
    try:
        auth_user = await client.auth.get_user(token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials") from exc

    if not auth_user or not auth_user.user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")

    sup_user = auth_user.user
    email = sup_user.email or (sup_user.user_metadata or {}).get("email")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User email missing in token")

    # Ensure local provisioning (idempotent)
    db_user = await ensure_user_provisioned(sup_user.id, email, (sup_user.user_metadata or {}).get("full_name"))
    # Re-fetch typed (optional improvement) or build minimal identity
    typed = await get_profile_by_supabase_id(sup_user.id)
    role = (typed.get("role") if typed else db_user.get("role")) or "student"

    current = CurrentUser(id=db_user["id"], email=email, role=role)  # type: ignore[arg-type]

    request_id = request.headers.get("X-Request-Id") or request.headers.get("X-Request-ID")
    if request_id:
        # Attach to state for downstream usage
        request.state.request_id = request_id
    logger.info(
        "auth_resolved user_id=%s email=%s role=%s request_id=%s path=%s",  # structured log compatible
        current.id,
        current.email,
        current.role,
        request_id,
        request.url.path,
    )
    return current


async def get_current_user_from_cookie(
    request: Request,
    claims: dict[str, Any] = Depends(get_current_claims),
) -> CurrentUser:
    """Verify a browser cookie (or bearer) token and return typed CurrentUser.

    This dependency is intended for use on protected paths where the frontend
    stores the access token as a cookie. Use in endpoints like:

        @router.get(...)
        async def protected(endpoint_user: CurrentUser = Depends(get_current_user_from_cookie)):
            ...
    """
    user_id = claims.get("sub")
    email = claims.get("email") or (claims.get("user_metadata") or {}).get("email") or ""
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token: missing subject")

    # Ensure local provisioning (idempotent)
    db_user = await ensure_user_provisioned(user_id, email, (claims.get("user_metadata") or {}).get("full_name"))
    typed = await get_profile_by_supabase_id(user_id)
    role = (typed.get("role") if typed else db_user.get("role")) or "student"

    current = CurrentUser(id=db_user["id"], email=email, role=role)  # type: ignore[arg-type]

    request_id = request.headers.get("X-Request-Id") or request.headers.get("X-Request-ID")
    if request_id:
        request.state.request_id = request_id
    logger.info(
        "cookie_auth_resolved user_id=%s email=%s role=%s request_id=%s path=%s",
        current.id,
        current.email,
        current.role,
        request_id,
        request.url.path,
    )
    return current


async def get_current_user_with_refresh(
    request: Request,
    response: Response,
    claims: dict[str, Any] = Depends(get_current_claims),
) -> CurrentUser:
    """Enhanced dependency that handles automatic token refresh.
    
    This checks if the access token is close to expiring and automatically
    refreshes it using the refresh token if available. Sets new cookies
    with updated tokens.
    """
    from fastapi import Response
    
    # Get current user from claims
    user_id = claims.get("sub")
    email = claims.get("email") or (claims.get("user_metadata") or {}).get("email") or ""
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token: missing subject")

    # Check if we should refresh the token
    access_token = request.cookies.get(ACCESS_COOKIE_NAME)
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    
    if access_token and refresh_token:
        try:
            new_tokens = await refresh_tokens_if_needed(access_token, refresh_token)
            if new_tokens:
                # Set new cookies with refreshed tokens
                set_auth_cookies(response, new_tokens)
                logger.info(f"Auto-refreshed tokens for user {user_id}")
        except Exception as e:
            # Log but don't fail the request - use existing token
            logger.warning(f"Failed to auto-refresh token for user {user_id}: {e}")

    # Ensure local provisioning (idempotent)
    db_user = await ensure_user_provisioned(user_id, email, (claims.get("user_metadata") or {}).get("full_name"))
    typed = await get_profile_by_supabase_id(user_id)
    role = (typed.get("role") if typed else db_user.get("role")) or "student"

    current = CurrentUser(id=db_user["id"], email=email, role=role)  # type: ignore[arg-type]

    request_id = request.headers.get("X-Request-Id") or request.headers.get("X-Request-ID")
    if request_id:
        request.state.request_id = request_id
    logger.info(
        "auth_with_refresh_resolved user_id=%s email=%s role=%s request_id=%s path=%s",
        current.id,
        current.email,
        current.role,
        request_id,
        request.url.path,
    )
    return current


def require_role(*roles: str) -> Callable:
    """Factory returning dependency enforcing that user has one of the roles.

    Admin roles always pass. Empty roles -> no restriction (returns current user).
    """

    normalized = {r.lower() for r in roles if r}

    async def _checker(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not normalized:  # no specific roles required
            return current
        if current.role.lower() in normalized or current.role.lower() in _admin_roles():
            return current
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    return _checker


def require_admin() -> Callable:
    return require_role("admin")
