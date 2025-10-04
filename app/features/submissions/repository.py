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

<<<<<<< HEAD
    async def list_tests(self, question_id: str) -> List[Dict[str, Any]]:
        client = await get_supabase()
        tests: List[Dict[str, Any]] = []
        # Gather tests from all known tables (legacy compatibility). Do not stop at the
        # first non-empty table — some questions may have rows in both `question_tests`
        # and `tests` and we want to include them all.
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
                # extend rather than replace so we collect rows from both tables
                tests.extend(resp.data)
        normalised: List[Dict[str, Any]] = []
        for index, test in enumerate(tests or []):
            raw_order = test.get("order_index")
            try:
                order_index = int(raw_order)
            except (TypeError, ValueError):
                order_index = index
            normalised.append(
                {
                    "id": test.get("id"),
                    "question_id": question_id,
                    "input": test.get("input", ""),
                    "expected": test.get("expected", ""),
                    "visibility": test.get("visibility"),
                    "order_index": order_index,
                    "expected_hash": test.get("expected_hash"),
                    "compare_mode": test.get("compare_mode"),
                    "compare_config": test.get("compare_config") or {},
                    "_position": index,
                }
            )
        normalised.sort(key=lambda t: (t.get("order_index", 0), t.get("_position", 0)))
        for entry in normalised:
            entry.pop("_position", None)
        return normalised


=======
>>>>>>> acf079eb3553ddd1e34eea9f50ab734671512fe4
submissions_repository = SubmissionsRepository()

__all__ = ["submissions_repository", "SubmissionsRepository"]
