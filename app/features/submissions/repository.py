from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.DB.supabase import get_supabase


class SubmissionsRepository:
    """Lightweight data access helpers for question bundles and tests."""

    _QUESTION_TABLE = "questions"
    _TEST_TABLES = ("question_tests", "tests")

    async def get_question(self, question_id: str) -> Optional[Dict[str, Any]]:
        client = await get_supabase()
        resp = await client.table(self._QUESTION_TABLE).select("*").eq("id", question_id).limit(1).execute()
        rows = resp.data or []
        return rows[0] if rows else None

    async def list_tests(self, question_id: str) -> List[Dict[str, Any]]:
        client = await get_supabase()
        tests: List[Dict[str, Any]] = []
        for table in self._TEST_TABLES:
            try:
                resp = await (
                    client.table(table)
                    .select("*")
                    .eq("question_id", question_id)
                    .execute()
                )
            except Exception:  # pragma: no cover - fallback for legacy table name
                continue
            if resp.data:
                tests = resp.data
                break
        normalised: List[Dict[str, Any]] = []
        for index, test in enumerate(tests or []):
            normalised.append(
                {
                    "id": test.get("id"),
                    "question_id": question_id,
                    "input": test.get("input", ""),
                    "expected": test.get("expected", ""),
                    "visibility": (test.get("visibility") or "public").lower(),
                    "order_index": index,
                }
            )
        # Ensure deterministic ordering: public first, then by original order
        normalised.sort(key=lambda t: (t.get("visibility") != "public", t.get("order_index", 0)))
        return normalised


submissions_repository = SubmissionsRepository()

__all__ = ["submissions_repository", "SubmissionsRepository"]
