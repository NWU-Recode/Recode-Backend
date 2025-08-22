from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from app.common.deps import get_current_user, require_admin, CurrentUser
from typing import Callable
from .schemas import Profile as ProfileSchema, ProfileUpdate, ProfileRoleUpdate, PublicProfile
from .service import list_profiles, get_profile_by_id, update_profile, update_profile_role

router = APIRouter(prefix="/profiles", tags=["profiles"])

@router.get("/", response_model=list[ProfileSchema])
async def read_profiles(current_user: CurrentUser = Depends(require_admin)) -> list[ProfileSchema]:
    profiles = await list_profiles()
    return [ProfileSchema(**profile) for profile in profiles]

@router.get("/me", response_model=ProfileSchema)
async def read_current_profile(current_user: CurrentUser = Depends(get_current_user)) -> ProfileSchema:
    return ProfileSchema(**current_user.model_dump())

@router.put("/me", response_model=ProfileSchema)
async def update_current_profile(data: ProfileUpdate, current_user: CurrentUser = Depends(get_current_user)) -> ProfileSchema:
    updated = await update_profile(str(current_user.id), data)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return ProfileSchema(**updated)

@router.get("/{profile_id}", response_model=PublicProfile)
async def read_profile(profile_id: UUID, current_user: CurrentUser = Depends(get_current_user)) -> PublicProfile:
    prof = await get_profile_by_id(str(profile_id))
    if not prof:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return PublicProfile(**prof)

@router.put("/{profile_id}/role", response_model=ProfileSchema)
async def update_profile_role_endpoint(profile_id: UUID, role_data: ProfileRoleUpdate, current_user: CurrentUser = Depends(require_admin)) -> ProfileSchema:
    updated = await update_profile_role(str(profile_id), role_data)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return ProfileSchema(**updated)
