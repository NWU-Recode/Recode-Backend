"""Unified async Supabase client (single entry point) under canonical capitalized DB package.

Import using: from app.DB.supabase import get_supabase
"""
from __future__ import annotations

import asyncio
from typing import Optional
from supabase import AsyncClient, create_async_client
from app.core.config import get_settings

_settings = get_settings()
_client: Optional[AsyncClient] = None
_lock = asyncio.Lock()

async def get_supabase() -> AsyncClient:
    global _client
    if _client is not None:
        return _client
    async with _lock:
        if _client is None:
            _client = await create_async_client(_settings.supabase_url, _settings.supabase_key)
    return _client

# Backwards-compatible alias
get_client = get_supabase

__all__ = ["get_supabase", "get_client"]
