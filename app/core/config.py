from __future__ import annotations

import os
from functools import lru_cache
from dotenv import load_dotenv, find_dotenv

_env_path = find_dotenv(".env") or ".env"
load_dotenv(_env_path, override=True)


class Settings:
    """Central configuration (env driven)."""

    def __init__(self) -> None:
        # Supabase
        raw_url = os.getenv("SUPABASE_URL", "")
        self.supabase_url: str = raw_url.rstrip("/")
        self.supabase_anon_key: str = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY", "")
        self.supabase_key: str = self.supabase_anon_key  # alias
        self.supabase_service_role_key: str = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_SERVICE_KEY")
            or ""
        )
        # Database
        self.database_url: str = os.getenv("DATABASE_URL", "")
        # Judge0 / external
        self.judge0_api_url: str = os.getenv("JUDGE0_BASE_URL", "")
        self.judge0_api_key: str = os.getenv("JUDGE0_KEY", "")
        self.judge0_host: str = os.getenv("JUDGE0_HOST", "")
        # App meta
        self.app_name: str = "Recode Backend"
        self.debug: bool = os.getenv("DEBUG", "False").lower() == "true"
        # Dev convenience
        self.dev_auto_confirm: bool = os.getenv("DEV_AUTO_CONFIRM", "false").lower() == "true"
        # Cookie/session configuration
        self.cookie_domain: str | None = os.getenv("COOKIE_DOMAIN") or None
        self.cookie_secure: bool = os.getenv("COOKIE_SECURE", "true").lower() != "false"
        self.cookie_samesite: str = os.getenv("COOKIE_SAMESITE", "lax").capitalize()  # Lax|Strict|None

    @property
    def auth_base(self) -> str | None:
        return f"{self.supabase_url}/auth" if self.supabase_url else None
    # Backwards-compatible accessor (migrations URL removed)
    def get_database_url(self) -> str:
        return self.database_url


@lru_cache()
def get_settings() -> Settings:
    return Settings()


