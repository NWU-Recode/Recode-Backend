from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from app.DB.supabase import get_supabase


class CodeResultsRepository:
    async def _client(self):
        return await get_supabase()

    async def create_submission(
        self,
        *,
        user_id: int,
        language_id: int,
        source_code: str,
        judge0_token: Optional[str],
        stdin: Optional[str] = None,
        expected_output: Optional[str] = None,
    ) -> Optional[str]:
        client = await self._client()
        submission_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        payload: Dict[str, Any] = {
            "id": submission_id,
            "user_id": user_id,
            "source_code": source_code,
            "language_id": language_id,
            "stdin": stdin,
            "expected_output": expected_output,
            "judge0_token": judge0_token,
            "status": "completed",
            "created_at": now_iso,
            "completed_at": now_iso,
        }
        try:
            resp = await client.table("code_submissions").insert(payload).execute()
        except Exception:
            return None
        data = getattr(resp, "data", None)
        if data:
            first = data[0] if isinstance(data, list) else data
            return str(first.get("id", submission_id))
        return submission_id

    async def insert_results(
        self,
        submission_id: str,
        results: Iterable[Dict[str, Any]],
    ) -> None:
        records = []
        for item in results:
            record = dict(item)
            record.setdefault("id", str(uuid.uuid4()))
            record.setdefault("submission_id", submission_id)
            record.setdefault("created_at", datetime.now(timezone.utc).isoformat())
            compile_meta = record.get("compile_output")
            metadata = record.pop("_metadata", None)
            if metadata is not None:
                merged = {"metadata": metadata}
                if compile_meta is not None:
                    merged["compile_output"] = compile_meta
                record["compile_output"] = json.dumps(merged)
            elif isinstance(compile_meta, (dict, list)):
                record["compile_output"] = json.dumps(compile_meta)
            records.append(record)
        if not records:
            return
        client = await self._client()
        try:
            await client.table("code_results").insert(records).execute()
        except Exception:
            return

    async def log_test_batch(
        self,
        *,
        user_id: int,
        language_id: int,
        source_code: str,
        judge0_token: Optional[str],
        test_records: Iterable[Dict[str, Any]],
    ) -> Optional[str]:
        submission_id = await self.create_submission(
            user_id=user_id,
            language_id=language_id,
            source_code=source_code,
            judge0_token=judge0_token,
        )
        if not submission_id:
            return None
        await self.insert_results(submission_id, test_records)
        return submission_id


code_results_repository = CodeResultsRepository()

__all__ = ["code_results_repository", "CodeResultsRepository"]
