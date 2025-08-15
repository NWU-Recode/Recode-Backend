"""User service functions (SQLAlchemy-backed)."""

from __future__ import annotations
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Optional
from uuid import UUID
from fastapi.concurrency import run_in_threadpool

from .models import User
from .schemas import UserCreate, UserUpdate, UserRoleUpdate


def list_users(db: Session) -> list[User]:
    """Return all users ordered by newest first (sync; run in threadpool in async paths)."""
    return db.query(User).order_by(User.created_at.desc()).all()


async def list_users_async(db: Session) -> list[User]:
    """Async wrapper executing the blocking ORM query in a threadpool."""
    return await run_in_threadpool(list_users, db)


def create_user_in_db_sync(supabase_id: str, user_data: UserCreate, db: Session) -> User:
    """Create a new user in the database (sync version)."""
    db_user = User(
        supabase_id=supabase_id,
        email=user_data.email,
        full_name=user_data.full_name,
        role="student",  # Default role
        is_active=True,
        is_superuser=False,
        email_verified=False
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


async def create_user_in_db(supabase_id: str, user_data: UserCreate, db: Session = None) -> User:
    """Create a new user in the database (async wrapper)."""
    if db is None:
        from app.DB.session import SessionLocal
        db = SessionLocal()
        close_db = True
    else:
        close_db = False
    
    try:
        return await run_in_threadpool(create_user_in_db_sync, supabase_id, user_data, db)
    finally:
        if close_db:
            db.close()


def get_user_by_supabase_id_sync(supabase_id: str, db: Session) -> Optional[User]:
    """Get user by Supabase ID (sync version)."""
    stmt = select(User).where(User.supabase_id == supabase_id)
    return db.scalar(stmt)


async def get_user_by_supabase_id(supabase_id: str, db: Session = None) -> Optional[User]:
    """Get user by Supabase ID (async wrapper)."""
    if db is None:
        from app.DB.session import SessionLocal
        db = SessionLocal()
        close_db = True
    else:
        close_db = False
    
    try:
        return await run_in_threadpool(get_user_by_supabase_id_sync, supabase_id, db)
    finally:
        if close_db:
            db.close()


def get_user_by_id_sync(user_id: UUID, db: Session) -> Optional[User]:
    """Get user by ID (sync version)."""
    return db.get(User, user_id)


async def get_user_by_id(user_id: UUID, db: Session = None) -> Optional[User]:
    """Get user by ID (async wrapper)."""
    if db is None:
        from app.DB.session import SessionLocal
        db = SessionLocal()
        close_db = True
    else:
        close_db = False
    
    try:
        return await run_in_threadpool(get_user_by_id_sync, user_id, db)
    finally:
        if close_db:
            db.close()


def update_user_sync(user_id: UUID, user_data: UserUpdate, db: Session) -> Optional[User]:
    """Update user profile (sync version)."""
    db_user = db.get(User, user_id)
    if not db_user:
        return None
    
    update_data = user_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_user, field, value)
    
    db.commit()
    db.refresh(db_user)
    return db_user


async def update_user(user_id: UUID, user_data: UserUpdate, db: Session = None) -> Optional[User]:
    """Update user profile (async wrapper)."""
    if db is None:
        from app.DB.session import SessionLocal
        db = SessionLocal()
        close_db = True
    else:
        close_db = False
    
    try:
        return await run_in_threadpool(update_user_sync, user_id, user_data, db)
    finally:
        if close_db:
            db.close()


def update_user_role_sync(user_id: UUID, role_data: UserRoleUpdate, db: Session) -> Optional[User]:
    """Update user role (admin only, sync version)."""
    db_user = db.get(User, user_id)
    if not db_user:
        return None
    
    db_user.role = role_data.role
    db.commit()
    db.refresh(db_user)
    return db_user


async def update_user_role(user_id: UUID, role_data: UserRoleUpdate, db: Session = None) -> Optional[User]:
    """Update user role (admin only, async wrapper)."""
    if db is None:
        from app.DB.session import SessionLocal
        db = SessionLocal()
        close_db = True
    else:
        close_db = False
    
    try:
        return await run_in_threadpool(update_user_role_sync, user_id, role_data, db)
    finally:
        if close_db:
            db.close()


def update_user_last_signin_sync(user_id: UUID, db: Session) -> bool:
    """Update user's last sign in time (sync version)."""
    from datetime import datetime, timezone
    
    db_user = db.get(User, user_id)
    if not db_user:
        return False
    
    db_user.last_sign_in = datetime.now(timezone.utc)
    db.commit()
    return True


async def update_user_last_signin(user_id: UUID, db: Session = None) -> bool:
    """Update user's last sign in time (async wrapper)."""
    if db is None:
        from app.DB.session import SessionLocal
        db = SessionLocal()
        close_db = True
    else:
        close_db = False
    
    try:
        return await run_in_threadpool(update_user_last_signin_sync, user_id, db)
    finally:
        if close_db:
            db.close()


# Placeholder for future Supabase-backed implementation if needed.
async def list_users_supabase():  # pragma: no cover - not wired
    raise NotImplementedError("Supabase users listing not implemented.")

