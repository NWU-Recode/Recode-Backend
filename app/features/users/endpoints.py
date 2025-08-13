"""User API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.service import get_current_user
from app.db.session import get_db
from .schemas import User as UserSchema
from .service import list_users

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserSchema])
def read_users(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> list[UserSchema]:
    """Return all users (requires authentication)."""
    return list_users(db)

