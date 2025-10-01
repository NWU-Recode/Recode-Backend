from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from app.DB.supabase import get_supabase

_SUMMARY_COLUMNS = {
    "status_id",
    "stdout",
    "stderr",
    "time",
    "wall_time",
    "memory",
    "compile_output",
    "message",
    "exit_code",
    "exit_signal",
    "wall_time_limit",
    "wall_extra_time_limit",
    "cpu_time_limit",
    "cpu_extra_time_limit",
    "cpu_extra_time",
    "memory_limit",
    "stack_limit",
    "max_processes_and_or_threads",
    "max_file_size",
    "number_of_runs",
    "enable_per_process_and_thread_time_limit",
    "redirect_stderr_to_stdout",
    "enable_network",
    "enable_warnings",
    "compiler_options",
    "command_line_arguments",
    "callback_url",
    "additional_files",
    "finished_at",
    "results_id",
    "challenge_id",
}


def _iso_timestamp(value: Any) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    return str(value)


def _serialise_summary_value(key: str, value: Any) -> Any:
    if value is None:
        return None
    if key in {"stdout", "stderr", "compile_output", "message"}:
        if isinstance(value, (list, tuple)):
            return "\n".join(str(item) for item in value if item is not None)
        if isinstance(value, (dict, set)):
            return json.dumps(value)
        return str(value)
    if key == "additional_files" and isinstance(value, (dict, list)):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return value


class CodeResultsRepository:
    async def _client(self):
        return await get_supabase()

    async def create_submission(
        self,
        *,
        user_id: int,
        language_id: int,
        source_code: str,
        token: Optional[str],
        stdin: Optional[str] = None,
        expected_output: Optional[str] = None,
        challenge_id: Optional[str] = None,
        question_id: Optional[str] = None,
        summary: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        client = await self._client()
        summary = dict(summary or {})
        now_iso = datetime.now(timezone.utc).isoformat()

        finished_at = summary.get("finished_at")
        if finished_at is not None:
            summary["finished_at"] = _iso_timestamp(finished_at)

        additional_meta = summary.get("additional_files")
        if question_id:
            payload_meta = dict(additional_meta or {})
            payload_meta.setdefault("question_id", question_id)
            summary["additional_files"] = payload_meta

        payload: Dict[str, Any] = {
            "user_id": user_id,
            "challenge_id": challenge_id,
            "source_code": source_code,
            "language_id": language_id,
            "stdin": stdin,
            "expected_output": expected_output,
            "token": token,
            "created_at": now_iso,
        }
        if "finished_at" not in summary:
            payload["finished_at"] = now_iso

        for key, value in summary.items():
            if key in _SUMMARY_COLUMNS:
                coerced = _serialise_summary_value(key, value)
                if coerced is not None:
                    payload[key] = coerced

        payload = {k: v for k, v in payload.items() if v is not None}

        try:
            resp = await client.table("code_submissions").insert(payload).execute()
        except Exception:
            return None

        data = getattr(resp, "data", None)
        if isinstance(data, list) and data:
            submission_id = data[0].get("id")
        elif isinstance(data, dict):
            submission_id = data.get("id")
        else:
            submission_id = None
        return str(submission_id) if submission_id is not None else None

    async def insert_results(
        self,
        submission_id: str,
        results: Iterable[Dict[str, Any]],
    ) -> None:
        records = []
        for item in results:
            record = dict(item)
            record.setdefault("submission_id", submission_id)
            created_at = record.get("created_at")
            if created_at is None:
                record["created_at"] = datetime.now(timezone.utc).isoformat()
            else:
                record["created_at"] = _iso_timestamp(created_at)
            token_value = record.pop("token", None)
            metadata = record.pop("_metadata", None)
            if metadata is not None or token_value is not None:
                meta_payload: Dict[str, Any] = {}
                if metadata is not None:
                    meta_payload["metadata"] = metadata
                if token_value is not None:
                    meta_payload["token"] = token_value
                compile_meta = record.get("compile_output")
                if compile_meta is not None:
                    meta_payload["compile_output"] = compile_meta
                record["compile_output"] = json.dumps(meta_payload)
            elif isinstance(record.get("compile_output"), (dict, list)):
                record["compile_output"] = json.dumps(record["compile_output"])
            records.append({k: v for k, v in record.items() if v is not None})
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
        token: Optional[str],
        test_records: Iterable[Dict[str, Any]],
        summary: Optional[Dict[str, Any]] = None,
        stdin: Optional[str] = None,
        expected_output: Optional[str] = None,
        challenge_id: Optional[str] = None,
        question_id: Optional[str] = None,
    ) -> Optional[str]:
        records_list = list(test_records)
        effective_summary = dict(summary or {})
        effective_summary.setdefault("number_of_runs", len(records_list) or None)
        submission_id = await self.create_submission(
            user_id=user_id,
            language_id=language_id,
            source_code=source_code,
            token=token,
            stdin=stdin,
            expected_output=expected_output,
            challenge_id=challenge_id,
            question_id=question_id,
            summary=effective_summary,
        )
        if not submission_id:
            return None
        await self.insert_results(submission_id, records_list)
        return submission_id


code_results_repository = CodeResultsRepository()

__all__ = ["code_results_repository", "CodeResultsRepository"]
