"""Session forge."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

settings = get_settings()


def get_database_url() -> str:
    return settings.get_database_url()

runtime_url = get_database_url()
if not runtime_url:
    raise RuntimeError("DATABASE_URL not configured")

connect_args = {"sslmode": "require"} if "sslmode=" not in runtime_url else {}

engine = create_engine(
    runtime_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    pool_recycle=300,
    echo=settings.debug,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
