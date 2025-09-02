from __future__ import annotations

import os
from functools import lru_cache
from dotenv import load_dotenv, find_dotenv

_env_path = find_dotenv(".env") or ".env"
load_dotenv(_env_path, override=True)


class Settings:
    def __init__(self) -> None:
        raw_url = os.getenv("SUPABASE_URL", "")
        self.supabase_url = raw_url.rstrip("/")
        self.supabase_anon_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY", "")
        self.supabase_key = self.supabase_anon_key
        self.supabase_service_role_key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_SERVICE_KEY")
            or ""
        )
        self.supabase_jwt_secret = os.getenv("SUPABASE_JWT_SECRET") or None
        self.database_url = os.getenv("DATABASE_URL", "")
        self.judge0_api_url = os.getenv("JUDGE0_BASE_URL", "")
        self.judge0_api_key = os.getenv("JUDGE0_KEY", "")
        self.judge0_host = os.getenv("JUDGE0_HOST", "")
        # Hugging Face / AI generation
        self.hf_api_token = os.getenv("HUGGINGFACE_API_TOKEN", "")
        self.hf_model_id = os.getenv("HF_MODEL_ID", "mistralai/Mistral-7B-Instruct-v0.3")
        try:
            self.hf_timeout_ms = int(os.getenv("HF_TIMEOUT_MS", "30000"))
        except Exception:
            self.hf_timeout_ms = 30000
        self.app_name = "Recode Backend"
        self.debug = os.getenv("DEBUG", "False").lower() == "true"
        self.dev_auto_confirm = os.getenv("DEV_AUTO_CONFIRM", "false").lower() == "true"
        self.cookie_domain = os.getenv("COOKIE_DOMAIN") or None
        self.cookie_secure = os.getenv("COOKIE_SECURE", "true").lower() != "false"
        self.cookie_samesite = os.getenv("COOKIE_SAMESITE", "lax").capitalize()

    @property
    def auth_base(self) -> str | None:
        return f"{self.supabase_url}/auth" if self.supabase_url else None

    def get_database_url(self) -> str:
        return self.database_url


@lru_cache()
def get_settings() -> Settings:
    return Settings()


