"""Supabase client utilities.

Provides:
- A lazily created, module-level cached **async** Supabase client via `get_supabase()`.
- An optional **sync** client `supabase_sync` if you need legacy sync calls.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from supabase import AsyncClient, create_async_client, create_client

from app.core.config import get_settings

_settings = get_settings()

# ---- Async client (singleton) ------------------------------------------------
_client_async: Optional[AsyncClient] = None
_client_lock = asyncio.Lock()


async def get_supabase() -> AsyncClient:
    """Return a cached `AsyncClient` instance (lazy-created, thread-safe)."""
    global _client_async
    if _client_async is not None:
        return _client_async

    async with _client_lock:
        if _client_async is None:
            try:
                _client_async = await create_async_client(
                    _settings.supabase_url, _settings.supabase_key
                )
            except Exception as exc:  # pragma: no cover (network/init failure)
                raise RuntimeError("Could not create Supabase async client") from exc
    return _client_async


# ---- Optional sync client (create once at import if you need it) -------------
# Safe to keep for code that still uses the sync SDK; remove if not needed.
supabase_sync = create_client(_settings.supabase_url, _settings.supabase_key)
