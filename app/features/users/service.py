"""User service functions (SQLAlchemy-backed)."""

from __future__ import annotations
from sqlalchemy.orm import Session
from .models import User
from fastapi.concurrency import run_in_threadpool


def list_users(db: Session) -> list[User]:
    """Return all users ordered by newest first (sync; run in threadpool in async paths)."""
    return db.query(User).order_by(User.created_at.desc()).all()


async def list_users_async(db: Session) -> list[User]:
    """Async wrapper executing the blocking ORM query in a threadpool."""
    return await run_in_threadpool(list_users, db)


# Placeholder for future Supabase-backed implementation if needed.
async def list_users_supabase():  # pragma: no cover - not wired
    raise NotImplementedError("Supabase users listing not implemented.")

