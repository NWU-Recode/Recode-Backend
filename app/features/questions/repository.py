from __future__ import annotations
from typing import Optional, Dict, Any, List
from uuid import UUID
from app.DB.supabase import get_supabase

class QuestionRepository:
    async def get_question(self, question_id: str) -> Optional[Dict[str, Any]]:
        client = await get_supabase()
        resp = client.table("questions").select("*").eq("id", question_id).single().execute()
        return resp.data or None

    async def upsert_attempt(self, attempt: Dict[str, Any]) -> Dict[str, Any]:
        client = await get_supabase()
        # If id provided treat as update, else insert
        if attempt.get("id"):
            aid = attempt.pop("id")
            resp = client.table("question_attempts").update(attempt).eq("id", aid).execute()
        else:
            resp = client.table("question_attempts").insert(attempt).execute()
        if not resp.data:
            raise RuntimeError("Failed to persist question attempt")
        return resp.data[0]

    async def mark_previous_not_latest(self, question_id: str, user_id: str):
        client = await get_supabase()
        client.table("question_attempts").update({"latest": False}).eq("question_id", question_id).eq("user_id", user_id).eq("latest", True).execute()

    async def get_existing_attempt(self, question_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        client = await get_supabase()
        resp = (
            client.table("question_attempts")
            .select("*")
            .eq("question_id", question_id)
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]
        return None

    async def find_by_code_hash(self, question_id: str, user_id: str, code_hash: str) -> Optional[Dict[str, Any]]:
        client = await get_supabase()
        resp = (
            client.table("question_attempts")
            .select("*")
            .eq("question_id", question_id)
            .eq("user_id", user_id)
            .eq("code_hash", code_hash)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]
        return None

    async def find_by_idempotency_key(self, question_id: str, user_id: str, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """Return existing attempt matching idempotency key (latest semantics implicit via unique constraint)."""
        client = await get_supabase()
        resp = (
            client.table("question_attempts")
            .select("*")
            .eq("question_id", question_id)
            .eq("user_id", user_id)
            .eq("idempotency_key", idempotency_key)
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]
        return None

    async def find_by_token(self, question_id: str, user_id: str, token: str) -> Optional[Dict[str, Any]]:
        client = await get_supabase()
        resp = (
            client.table("question_attempts")
            .select("*")
            .eq("question_id", question_id)
            .eq("user_id", user_id)
            .eq("judge0_token", token)
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]
        return None

    async def list_attempts_for_challenge(self, challenge_id: str, user_id: str) -> List[Dict[str, Any]]:
        client = await get_supabase()
        resp = (
            client.table("question_attempts")
            .select("*")
            .eq("user_id", user_id)
            .eq("challenge_id", challenge_id)
            .execute()
        )
        return resp.data or []

    async def list_latest_attempts_for_challenge(self, challenge_id: str, user_id: str) -> List[Dict[str, Any]]:
        client = await get_supabase()
        resp = (
            client.table("question_attempts")
            .select("*")
            .eq("user_id", user_id)
            .eq("challenge_id", challenge_id)
            .eq("latest", True)
            .execute()
        )
        return resp.data or []

question_repository = QuestionRepository()
