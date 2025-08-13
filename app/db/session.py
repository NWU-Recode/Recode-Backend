"""Database session utilities."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from supabase import AsyncClient

from .client import get_client


@asynccontextmanager
async def supabase_session() -> AsyncIterator[AsyncClient]:
    """Provide a Supabase client session."""
    client = await get_client()
    yield client
