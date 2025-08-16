from __future__ import annotations

import os
from functools import lru_cache
from dotenv import load_dotenv, find_dotenv

_env_path = find_dotenv(".env") or ".env"
load_dotenv(_env_path, override=True)


class Settings:
    """Central configuration (env driven)."""

    def __init__(self) -> None:
        self.supabase_url = os.getenv("SUPABASE_URL", "")
        self.supabase_key = os.getenv("SUPABASE_KEY", "")
        self.database_url = os.getenv("DATABASE_URL", "")
        self.database_url_migrations = os.getenv("DATABASE_URL_MIGRATIONS", "")
        self.judge0_api_url = os.getenv("JUDGE0_BASE_URL", "")
        self.judge0_api_key = os.getenv("JUDGE0_KEY", "")
        self.judge0_host = os.getenv("JUDGE0_HOST", "")
        self.app_name = "Recode Backend"
        self.debug = os.getenv("DEBUG", "False").lower() == "true"
        # Semester planning (plain challenges count used for milestone unlock logic)
        self.total_plain_challenges_semester = int(os.getenv("TOTAL_PLAIN_CHALLENGES_SEMESTER", "12"))

    def get_database_url(self, for_migrations: bool = False) -> str:
        if for_migrations and self.database_url_migrations:
            return self.database_url_migrations
        return self.database_url


@lru_cache()
def get_settings() -> Settings:
    return Settings()


