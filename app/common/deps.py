"""Shared FastAPI dependencies for authn/authz & request context."""

from __future__ import annotations

import logging
from uuid import UUID
from functools import lru_cache
from typing import Callable, Iterable, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr

from app.DB.supabase import get_supabase
from app.features.users.service import ensure_user_provisioned, get_user_schema_by_supabase_id

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
    typed = await get_user_schema_by_supabase_id(sup_user.id)
    role = (typed.role if typed else db_user.get("role")) or "student"

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
