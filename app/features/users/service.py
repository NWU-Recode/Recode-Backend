"""User service functions."""

from __future__ import annotations
from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from .models import User

def get_all_users(db: Session | None = None):
    created_here = False
    if db is None:
        db = SessionLocal()
        created_here = True
    try:
        return db.query(User).order_by(User.created_at.desc()).all()
    finally:
        if created_here:
            db.close()

from fastapi import HTTPException, status

from app.db.session import supabase_session


async def get_all_users() -> list[dict]:
    """Fetch all users from the Supabase ``users`` table."""
    async with supabase_session() as client:
        try:
            response = await client.table("users").select("*").execute()
        except Exception as exc:  # pragma: no cover - external failure
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch users",
            ) from exc
    return response.data or []
