from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status, Request
from uuid import UUID
from app.common.deps import (
    get_current_user_from_cookie,
    require_admin_cookie,
    get_current_user_with_refresh,
    CurrentUser,
)
from typing import Callable
from .schemas import Profile as ProfileSchema, ProfileUpdate, ProfileRoleUpdate, PublicProfile
from .service import list_profiles, get_profile_by_id, update_profile, update_profile_role

router = APIRouter(prefix="/profiles", tags=["profiles"])

@router.get("/", response_model=list[ProfileSchema])
async def read_profiles(current_user: CurrentUser = Depends(require_admin_cookie())) -> list[ProfileSchema]:
    """Admin-only: List all profiles (cookie auth)."""
    profiles = await list_profiles()
    return [ProfileSchema(**profile) for profile in profiles]

@router.get("/me", response_model=ProfileSchema)
async def read_current_profile(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user_with_refresh),
) -> ProfileSchema:
    """Authenticated user: Get their own full profile (auto-refresh if expiring).

    The auth dependency returns a minimal CurrentUser (id/email/role). We need to
    fetch the persisted profile row to satisfy the full ProfileSchema contract.
    """
    # Fetch full record by local UUID (current_user.id)
    from .service import get_profile_by_id  # local import to avoid circular at import time
    prof = await get_profile_by_id(str(current_user.id))
    if not prof:
        # Should not normally happen because provisioning occurs in auth deps
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return ProfileSchema(**prof)

@router.put("/me", response_model=ProfileSchema)
async def update_current_profile(
    data: ProfileUpdate,
    current_user: CurrentUser = Depends(get_current_user_from_cookie),
) -> ProfileSchema:
    """Authenticated user: Update their own profile (cookie auth)."""
    updated = await update_profile(str(current_user.id), data)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return ProfileSchema(**updated)

@router.get("/{profile_id}", response_model=PublicProfile)
async def read_profile(
    profile_id: UUID,
    current_user: CurrentUser = Depends(get_current_user_from_cookie),
) -> PublicProfile:
    """Authenticated user: Get a public profile by ID (cookie auth)."""
    prof = await get_profile_by_id(str(profile_id))
    if not prof:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return PublicProfile(**prof)

@router.put("/{profile_id}/role", response_model=ProfileSchema)
async def update_profile_role_endpoint(
    profile_id: UUID,
    role_data: ProfileRoleUpdate,
    current_user: CurrentUser = Depends(require_admin_cookie()),
) -> ProfileSchema:
    """Admin-only: Update a user's role (cookie auth)."""
    updated = await update_profile_role(str(profile_id), role_data)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return ProfileSchema(**updated)
