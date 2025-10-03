from __future__ import annotations

from typing import Any, Dict, Optional

from app.DB.supabase import get_supabase


class SubmissionsRepository:
    """Lightweight data access helpers for question bundles."""

    _QUESTION_TABLE = "questions"

    async def get_question(self, question_id: str) -> Optional[Dict[str, Any]]:
        client = await get_supabase()
        resp = await client.table(self._QUESTION_TABLE).select("*").eq("id", question_id).limit(1).execute()
        rows = resp.data or []
        return rows[0] if rows else None

submissions_repository = SubmissionsRepository()

__all__ = ["submissions_repository", "SubmissionsRepository"]
