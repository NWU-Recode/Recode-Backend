"""Supabase client utilities.

This module exposes helpers to create and access a global asynchronous
Supabase client. A single client instance is reused across requests to
avoid connection overhead.
"""

from __future__ import annotations

from typing import Optional

from supabase import AsyncClient, create_async_client

from app.core.config import SUPABASE_KEY, SUPABASE_URL

_supabase: Optional[AsyncClient] = None


async def get_client() -> AsyncClient:
    """Return a global :class:`~supabase.AsyncClient` instance.

    The client is created lazily on the first call. Subsequent calls reuse
    the existing instance.

    Raises
    ------
    RuntimeError
        If the client cannot be created.
    """
    global _supabase
    if _supabase is None:
        try:
            _supabase = await create_async_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception as exc:  # pragma: no cover - network failure
            raise RuntimeError("Could not create Supabase client") from exc
    return _supabase
from app.core.config import get_settings
from supabase import create_client

settings = get_settings()

supabase = create_client(settings.supabase_url, settings.supabase_key)
