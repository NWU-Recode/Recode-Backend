"""Supabase session utilities for authentication and user management."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from supabase import AsyncClient, create_async_client
from app.Core.config import get_settings

_settings = get_settings()

async def get_client() -> AsyncClient:
    return await create_async_client(
        _settings.supabase_url, 
        _settings.supabase_key
    )

@asynccontextmanager
async def supabase_session() -> AsyncIterator[AsyncClient]:
    #Provide a Supabase client session
    client = await get_client()
    try:
        yield client
    finally:
        pass