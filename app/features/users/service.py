"""User service functions (SQLAlchemy-backed)."""

from __future__ import annotations
from sqlalchemy.orm import Session
from .models import User


def list_users(db: Session) -> list[User]:
    """Return all users ordered by newest first."""
    return db.query(User).order_by(User.created_at.desc()).all()


# Placeholder for future Supabase-backed implementation if needed.
async def list_users_supabase():  # pragma: no cover - not wired
    raise NotImplementedError("Supabase users listing not implemented.")

