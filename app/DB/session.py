#app\DB\session.py
"""Session forge."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import time
import logging

from app.Core.config import get_settings

settings = get_settings()


def get_database_url() -> str:
    return settings.get_database_url()

runtime_url = get_database_url()
if not runtime_url:
    raise RuntimeError("DATABASE_URL not configured")

connect_args = {"sslmode": "require"} if "sslmode=" not in runtime_url else {}

# Tunables (clamped to expose issues faster)
_pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
_max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "5"))
_pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "5"))
_connect_timeout = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))

# Add connect_timeout to driver connect args
connect_args = {**connect_args, "connect_timeout": _connect_timeout}

engine = create_engine(
    runtime_url,
    pool_pre_ping=True,
    pool_size=_pool_size,
    max_overflow=_max_overflow,
    pool_timeout=_pool_timeout,
    pool_recycle=300,
    echo=settings.debug,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


logger = logging.getLogger("db.session")


def get_db():
    t0 = time.perf_counter()
    db = SessionLocal()
    acquire_ms = int((time.perf_counter() - t0) * 1000)
    # Lightweight visibility into pool waits
    if acquire_ms > 50:
        logger.warning("db_acquire_ms=%d", acquire_ms)
    try:
        yield db
    finally:
        db.close()
        
get_sync_session = get_db

