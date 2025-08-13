from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings

settings = get_settings()

def get_database_url(for_migrations: bool = False) -> str:
    """Return DB URL (runtime pooled vs direct migrations)."""
    return settings.get_database_url(for_migrations=for_migrations)

runtime_url = get_database_url(False)
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

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models (Alem bic imports this)
Base = declarative_base()

# FastAPI dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
