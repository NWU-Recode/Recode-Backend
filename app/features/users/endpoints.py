"""User API endpoints (Supabase-backed)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID

from app.common.deps import get_current_user, require_admin, CurrentUser
from .schemas import (
    User as UserSchema,
    UserUpdate,
    UserRoleUpdate,
    UserProfile,
)
from .service import (
    list_users,
    get_user_by_id,
    update_user,
    update_user_role,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserSchema])
async def read_users(current_user: CurrentUser = Depends(require_admin())) -> list[UserSchema]:
    """Return all users (admin only)."""
    return await list_users()

@router.get("/report/summary", summary="Example reporting endpoint (admin)")
async def reporting_summary(current_user: CurrentUser = Depends(require_admin())):
    """Demonstrates require_admin applied to a reporting-style endpoint.

    Returns simple aggregate counts. Extend as needed.
    """
    try:
        rows = await list_users(limit=0)  # fetch nothing, just for example
        return {"user_count": len(rows)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to build summary: {e}")


@router.get("/me", response_model=UserSchema)
async def read_current_user(current_user: CurrentUser = Depends(get_current_user)) -> UserSchema:
    """Return current authenticated user's full record."""
    return current_user


@router.put("/me", response_model=UserSchema)
async def update_current_user(
    user_data: UserUpdate,
    current_user: CurrentUser = Depends(get_current_user),
) -> UserSchema:
    updated = await update_user(str(current_user.id), user_data)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return updated


@router.get("/{user_id}", response_model=UserProfile)
async def read_user(user_id: UUID, current_user: CurrentUser = Depends(get_current_user)) -> UserProfile:
    user = await get_user_by_id(str(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    # Shape to profile subset
    return {
        "id": user["id"],
        "full_name": user.get("full_name"),
        "avatar_url": user.get("avatar_url"),
        "bio": user.get("bio"),
        "role": user.get("role"),
        "created_at": user.get("created_at"),
    }


@router.put("/{user_id}/role", response_model=UserSchema)
async def update_user_role_endpoint(
    user_id: UUID,
    role_data: UserRoleUpdate,
    current_user: CurrentUser = Depends(require_admin()),
) -> UserSchema:
    updated = await update_user_role(str(user_id), role_data)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return updated

