from __future__ import annotations

import os
from functools import lru_cache
from dotenv import load_dotenv, find_dotenv

# Load .env from project root no matter where code runs (fallback to ".env")
_env_path = find_dotenv(".env") or ".env"
load_dotenv(_env_path, override=True)


class Settings:
        """Env siphon. One URL. No drama."""

        def __init__(self) -> None:
                self.supabase_url = os.getenv("SUPABASE_URL", "")
                self.supabase_key = os.getenv("SUPABASE_KEY", "")
                # Removed local database_url - using Supabase only
                self.judge0_api_url = os.getenv("JUDGE0_BASE_URL", "")
                self.judge0_api_key = os.getenv("JUDGE0_KEY", "")
                self.judge0_host = os.getenv("JUDGE0_HOST", "")
                self.app_name = "Recode Backend"
                self.debug = os.getenv("DEBUG", "False").lower() == "true"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# Legacy exports
_settings = get_settings()
SUPABASE_URL = _settings.supabase_url
SUPABASE_KEY = _settings.supabase_key
