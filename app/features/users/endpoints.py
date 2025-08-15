"""User API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.concurrency import run_in_threadpool
from uuid import UUID

from app.Auth.service import get_current_user, require_admin
from app.DB.session import get_db
from .schemas import (
    User as UserSchema, 
    UserUpdate, 
    UserRoleUpdate, 
    UserProfile
)
from .service import (
    list_users_async, 
    get_user_by_id, 
    update_user, 
    update_user_role
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserSchema])
async def read_users(
    db: Session = Depends(get_db),
    current_user=Depends(require_admin()),
) -> list[UserSchema]:
    """Return all users (admin only)."""
    return await list_users_async(db)


@router.get("/me", response_model=UserSchema)
async def read_current_user(
    current_user=Depends(get_current_user),
) -> UserSchema:
    """Get current user profile."""
    return current_user


@router.put("/me", response_model=UserSchema)
async def update_current_user(
    user_data: UserUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserSchema:
    """Update current user profile."""
    updated_user = await update_user(current_user.id, user_data, db)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return updated_user


@router.get("/{user_id}", response_model=UserProfile)
async def read_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> UserProfile:
    """Get user profile by ID (accessible to authenticated users)."""
    user = await get_user_by_id(user_id, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.put("/{user_id}/role", response_model=UserSchema)
async def update_user_role_endpoint(
    user_id: UUID,
    role_data: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin()),
) -> UserSchema:
    """Update user role (admin only)."""
    updated_user = await update_user_role(user_id, role_data, db)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return updated_user

