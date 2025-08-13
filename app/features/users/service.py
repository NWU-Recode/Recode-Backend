"""User service functions."""

from __future__ import annotations

from fastapi import HTTPException, status

from app.db.session import supabase_session


async def get_all_users() -> list[dict]:
    """Fetch all users from the Supabase ``users`` table."""
    async with supabase_session() as client:
        try:
            response = await client.table("users").select("*").execute()
        except Exception as exc:  # pragma: no cover - external failure
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch users",
            ) from exc
    return response.data or []
