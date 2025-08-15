from __future__ import annotations
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from .schemas import SubmissionCreate, SubmissionResultCreate
from app.DB.client import get_supabase


class SubmissionRepository:
    """Supabase-based async repository for code submissions & results (no local SQLAlchemy)."""

    async def create_submission(self, data: SubmissionCreate, user_id: str, judge0_token: str) -> Dict[str, Any]:
        client = await get_supabase()
        record = {
            "user_id": user_id,
            "question_id": data.question_id,
            "source_code": data.source_code,
            "language_id": data.language_id,
            "stdin": data.stdin,
            "expected_output": data.expected_output,
            "judge0_token": judge0_token,
            "status": "submitted",
        }
        resp = client.table("code_submissions").insert(record).execute()
        if not resp.data:
            raise RuntimeError("Failed to create submission")
        return resp.data[0]

    async def create_result(self, result: SubmissionResultCreate) -> Dict[str, Any]:
        client = await get_supabase()
        record = {
            "submission_id": result.submission_id,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "compile_output": result.compile_output,
            "execution_time": result.execution_time,
            "memory_used": result.memory_used,
            "status_id": result.status_id,
            "status_description": result.status_description,
        }
        resp = client.table("code_results").insert(record).execute()
        if not resp.data:
            raise RuntimeError("Failed to create result")
        return resp.data[0]

    async def get_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        client = await get_supabase()
        resp = client.table("code_submissions").select("*").eq("judge0_token", token).single().execute()
        return resp.data or None

    async def get_with_results(self, submission_id: str) -> Optional[Dict[str, Any]]:
        client = await get_supabase()
        sub_resp = client.table("code_submissions").select("*").eq("id", submission_id).single().execute()
        if not sub_resp.data:
            return None
        res_resp = client.table("code_results").select("*").eq("submission_id", submission_id).order("created_at", desc=True).execute()
        return {"submission": sub_resp.data, "results": res_resp.data or []}

    async def list_user_submissions(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        client = await get_supabase()
        resp = (
            client.table("code_submissions")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data or []

    async def delete_submission(self, submission_id: str, user_id: str) -> bool:
        client = await get_supabase()
        # Ownership check
        existing = client.table("code_submissions").select("id,user_id").eq("id", submission_id).single().execute().data
        if not existing or str(existing.get("user_id")) != str(user_id):
            return False
        resp = client.table("code_submissions").delete().eq("id", submission_id).execute()
        return bool(resp.data)

    async def language_statistics(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        client = await get_supabase()
        query = client.table("code_submissions").select("language_id")
        if user_id:
            query = query.eq("user_id", user_id)
        resp = query.execute()
        rows = resp.data or []
        counts: Dict[int, int] = {}
        for r in rows:
            lid = r.get("language_id")
            if lid is None:
                continue
            counts[lid] = counts.get(lid, 0) + 1
        return [
            {"language_id": k, "submission_count": v}
            for k, v in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        ]

    async def update_submission_status(self, submission_id: str, status: str, completed_at: Optional[datetime] = None) -> bool:
        client = await get_supabase()
        update_fields: Dict[str, Any] = {"status": status}
        if completed_at:
            update_fields["completed_at"] = completed_at.isoformat()
        resp = client.table("code_submissions").update(update_fields).eq("id", submission_id).execute()
        return bool(resp.data)

    async def get_submission_by_id(self, submission_id: str) -> Optional[Dict[str, Any]]:
        client = await get_supabase()
        resp = client.table("code_submissions").select("*").eq("id", submission_id).single().execute()
        return resp.data or None


submission_repository = SubmissionRepository()
