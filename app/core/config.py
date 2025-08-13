"""Application configuration settings."""

from __future__ import annotations

import os
from functools import lru_cache
from dotenv import load_dotenv, find_dotenv

# Load .env from project root no matter where code runs (fallback to ".env")
_env_path = find_dotenv(".env") or ".env"
load_dotenv(_env_path, override=True)


class Settings:
    """Application settings loaded from environment variables.

    Database URL strategy (Supabase):
      - DATABASE_URL            → runtime / pooled (e.g. PgBouncer 6543)
      - DATABASE_URL_MIGRATIONS → direct / unpooled (e.g. 5432) for Alembic
      - DATABASE_URL_DIRECT     → legacy synonym for migrations

    If only one is provided we reuse it for both, but having the dedicated
    migrations URL avoids issues with prepared statements on PgBouncer.
    """

    def __init__(self) -> None:
        # Supabase
        self.supabase_url: str = os.getenv("SUPABASE_URL", "")
        self.supabase_key: str = os.getenv("SUPABASE_KEY", "")

        # Database URLs
        self.database_url_runtime: str = os.getenv("DATABASE_URL", "")
        self.database_url_migrations: str = (
            os.getenv("DATABASE_URL_MIGRATIONS", "")
            or os.getenv("DATABASE_URL_DIRECT", "")
        )

        # Backwards compatibility attributes (old code may still reference these)
        self.database_url = self.database_url_runtime
        self.database_url_direct = self.database_url_migrations

        # Judge0
        self.judge0_api_url: str = os.getenv("JUDGE0_BASE_URL", "")
        self.judge0_api_key: str = os.getenv("JUDGE0_KEY", "")
        self.judge0_host: str = os.getenv("JUDGE0_HOST", "")

        # App
        self.app_name: str = "Recode Backend"
        self.debug: bool = os.getenv("DEBUG", "False").lower() == "true"

    def get_database_url(self, for_migrations: bool = False) -> str:
        """Return appropriate DB URL.

        :param for_migrations: When True prefer the direct (5432) URL.
        """
        if for_migrations:
            return self.database_url_migrations or self.database_url_runtime
        return self.database_url_runtime


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# --- Backwards-compat module-level constants (keep older imports working) ---
_settings = get_settings()
SUPABASE_URL = _settings.supabase_url
SUPABASE_KEY = _settings.supabase_key
