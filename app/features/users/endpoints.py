"""User API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth.service import get_current_user
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .schemas import User
from .service import get_all_users
from app.db.base import get_db

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[User])
async def read_users(current_user=Depends(get_current_user)) -> list[User]:
    """Return all users from the database."""
    return await get_all_users()
def read_users(db: Session = Depends(get_db)):
    return get_all_users(db)
