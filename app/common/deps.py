"""Shared FastAPI dependencies for authentication, authorization, and context."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Callable

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr

from app.DB.supabase import get_supabase
from app.features.profiles.service import ensure_profile_provisioned as ensure_user_provisioned
from app.Auth.deps import get_current_claims
from app.Auth.service import refresh_tokens_if_needed, set_auth_cookies, ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME


logger = logging.getLogger("auth.deps")
security = HTTPBearer(auto_error=True)


class CurrentUser(BaseModel):
    """Minimal user identity shared across endpoints."""
    id: int
    email: EmailStr
    role: str


@lru_cache()
def _admin_roles() -> set[str]:
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
    import asyncio, os, time
    client = await get_supabase()
    token = credentials.credentials
    try:
        # Clamp whoami to avoid 30s stalls
        t0 = time.perf_counter()
        whoami_timeout = float(os.getenv("AUTH_WHOAMI_TIMEOUT", "5"))
        auth_user = await asyncio.wait_for(client.auth.get_user(token), timeout=whoami_timeout)
        ms = int((time.perf_counter() - t0) * 1000)
        if ms > 50:
            logger.info("auth.get_user_ms=%d", ms)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials") from exc

    if not auth_user or not auth_user.user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")

    sup_user = auth_user.user
    email = sup_user.email or (sup_user.user_metadata or {}).get("email")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User email missing in token")

    # Ensure local provisioning (idempotent) and avoid a second fetch
    t1 = time.perf_counter()
    db_user = await ensure_user_provisioned(sup_user.id, email, (sup_user.user_metadata or {}).get("full_name"))
    t2 = time.perf_counter()
    role = (db_user.get("role") if isinstance(db_user, dict) else None) or "student"

    current = CurrentUser(id=db_user["id"], email=email, role=role)  # type: ignore[arg-type]

    request_id = request.headers.get("X-Request-Id") or request.headers.get("X-Request-ID")
    if request_id:
        request.state.request_id = request_id
    logger.info(
        "auth_resolved user_id=%s email=%s role=%s request_id=%s path=%s",
        current.id,
        current.email,
        current.role,
        request_id,
        request.url.path,
    )
    try:
        logger.info("auth_spans_ms whoami=%s provision=%s", None, int((t2 - t1) * 1000))
    except Exception:
        pass
    return current


async def get_current_user_from_cookie(
    request: Request,
    claims: dict[str, Any] = Depends(get_current_claims),
) -> CurrentUser:
    """Verify a browser cookie (or bearer) token and return typed CurrentUser.

    Optimizations:
      * Cache the resolved user on ``request.state.current_user``
      * Return the cached user if a previous dependency resolved it
    """
    cached: CurrentUser | None = getattr(request.state, "current_user", None)
    if cached is not None:
        return cached

    user_id = claims.get("sub")
    email = claims.get("email") or (claims.get("user_metadata") or {}).get("email") or ""
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token: missing subject")

    try:
        # Ensure local provisioning (idempotent) and avoid redundant fetch
        db_user = await ensure_user_provisioned(user_id, email, (claims.get("user_metadata") or {}).get("full_name"))
        role = (db_user.get("role") if isinstance(db_user, dict) else None) or "student"

        current = CurrentUser(id=db_user["id"], email=email, role=role)  # type: ignore[arg-type]
        request.state.current_user = current  # type: ignore[attr-defined]

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
    except Exception as e:
        logger.error("Error resolving user from cookie: %s", str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to resolve user")



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

    access_token = request.cookies.get(ACCESS_COOKIE_NAME)
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    
    if access_token and refresh_token:
        try:
            new_tokens = await refresh_tokens_if_needed(access_token, refresh_token)
            if new_tokens:
                set_auth_cookies(response, new_tokens)
                logger.info(f"Auto-refreshed tokens for user {user_id}")
        except Exception as e:
            logger.warning(f"Failed to auto-refresh token for user {user_id}: {e}")

    # Ensure local provisioning (idempotent) and avoid redundant fetch
    db_user = await ensure_user_provisioned(user_id, email, (claims.get("user_metadata") or {}).get("full_name"))
    role = (db_user.get("role") if isinstance(db_user, dict) else None) or "student"

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

def require_role(*roles: str, use_cookie: bool = False) -> Callable:
    """Factory returning dependency enforcing that user has one of the roles.

    Args:
      roles: Allowed roles (case-insensitive). Empty -> no restriction.
      use_cookie: If True, base resolution on cookie workflow; else bearer header.
    """
    normalized = {r.lower() for r in roles if r}

    base_dep = get_current_user_from_cookie if use_cookie else get_current_user

    async def _checker(current: CurrentUser = Depends(base_dep)) -> CurrentUser:
        if not normalized:
            return current
        role_l = current.role.lower()
        if role_l in normalized or role_l in _admin_roles():
            return current
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    return _checker


def require_admin(use_cookie: bool = False) -> Callable:
    return require_role("admin", use_cookie=use_cookie)


def require_admin_cookie() -> Callable:
    async def dependency(user: CurrentUser = Depends(get_current_user_from_cookie)) -> CurrentUser:
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="Not authorized as admin")
        return user

    return dependency


def require_lecturer(use_cookie: bool = False) -> Callable:
    return require_role("lecturer", use_cookie=use_cookie)


def require_lecturer_cookie() -> Callable:
    async def dependency(user: CurrentUser = Depends(get_current_user_from_cookie)) -> CurrentUser:
        if user.role != "lecturer":
            raise HTTPException(status_code=403, detail="Not authorized as lecturer")
        return user

    return dependency


def require_admin_or_lecturer_cookie() -> Callable:
    async def dependency(user: CurrentUser = Depends(get_current_user_from_cookie)) -> CurrentUser:
        if user.role in {"admin", "lecturer"}:
            return user
        raise HTTPException(status_code=403, detail="Not authorized as admin or lecturer")

    return dependency

