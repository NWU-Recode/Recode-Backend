"""Supabase session utilities (optional, used outside SQLAlchemy paths)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

# If you actually use supabase-py v2 async client, wire it here.
# Placeholder import to avoid breaking builds if not installed everywhere:
try:
    from supabase import AsyncClient  # type: ignore
except Exception:  # pragma: no cover
    AsyncClient = object  # fallback to avoid import errors

# Implement your own factory returning an AsyncClient instance.
# For now this is a stub so you can wire it later without blocking the rebase.
async def get_client() -> AsyncClient:  # type: ignore
    raise NotImplementedError("Wire up Supabase AsyncClient creation here.")

@asynccontextmanager
async def supabase_session() -> AsyncIterator[AsyncClient]:  # type: ignore
    """Provide a Supabase client session."""
    client = await get_client()
    try:
        yield client
    finally:
        # add any client cleanup if needed
        ...
# await client.close()  # type: ignore