from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status, Request

from app.common.deps import (
    get_current_user,
    require_admin,
    require_lecturer,
    require_role,
    CurrentUser,
)
from typing import Callable
from .schemas import Profile as ProfileSchema, ProfileUpdate, ProfileRoleUpdate, PublicProfile
from .service import list_profiles, get_profile_by_id, update_profile, update_profile_role

router = APIRouter(prefix="/profiles", tags=["profiles"])

@router.get("/", response_model=list[ProfileSchema])
async def read_profiles(current_user: CurrentUser = Depends(require_role('admin','lecturer')) ) -> list[ProfileSchema]:
    """Lecturer or Admin: List all profiles (bearer token)."""
    profiles = await list_profiles()
    return [ProfileSchema(**profile) for profile in profiles]

@router.get("/me", response_model=ProfileSchema)
async def read_current_profile(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> ProfileSchema:
    """Authenticated user: Get their own full profile (auto-refresh if expiring).

    The auth dependency returns a minimal CurrentUser (id/email/role). We need to
    fetch the persisted profile row to satisfy the full ProfileSchema contract.
    """
    prof = await get_profile_by_id(current_user.id)

    if not prof:
        # Should not normally happen because provisioning occurs in auth deps
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return ProfileSchema(**prof)

@router.put("/me", response_model=ProfileSchema)
async def update_current_profile(
    data: ProfileUpdate,
    current_user: CurrentUser = Depends(get_current_user),
) -> ProfileSchema:
    """Authenticated user: Update their own profile (bearer token)."""

    updated = await update_profile(current_user.id, data)

    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return ProfileSchema(**updated)

@router.get("/{profile_id}", response_model=PublicProfile)
async def read_profile(
    profile_id: int,
    current_user: CurrentUser = Depends(require_role('admin','lecturer')),
) -> PublicProfile:
    """Lecturer or Admin: Get a public profile by ID (bearer token)."""
    prof = await get_profile_by_id(profile_id)
    if not prof:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return PublicProfile(**prof)

@router.put("/{profile_id}/role", response_model=ProfileSchema)
async def update_profile_role_endpoint(
    profile_id: int,

    role_data: ProfileRoleUpdate,
    current_user: CurrentUser = Depends(require_admin()),
) -> ProfileSchema:
    """Admin-only: Update a user's role (bearer token)."""
    if current_user.id == profile_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins cannot modify their own roles."
        )

    updated = await update_profile_role(profile_id, role_data)

    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return ProfileSchema(**updated)

