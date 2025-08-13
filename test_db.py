from sqlalchemy import create_engine, text
from app.core.config import get_settings  # correct import

settings = get_settings()

if not settings.database_url:
    raise RuntimeError("DATABASE_URL missing. Check .env")

print("Testing DB host:", settings.database_url.split('@')[-1])

engine = create_engine(settings.database_url, pool_pre_ping=True)

with engine.connect() as conn:
    val = conn.execute(text("SELECT 1")).scalar()
    print("Result:", val)

print("DB OK")
