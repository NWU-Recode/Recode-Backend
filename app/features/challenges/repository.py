from __future__ import annotations
from typing import Optional, Dict, Any, List
from app.DB.client import get_supabase

class ChallengeRepository:
    async def get_challenge(self, challenge_id: str) -> Optional[Dict[str, Any]]:
        client = await get_supabase()
        resp = client.table("challenges").select("*").eq("id", challenge_id).single().execute()
        return resp.data or None

    async def get_challenge_questions(self, challenge_id: str) -> List[Dict[str, Any]]:
        client = await get_supabase()
        resp = client.table("questions").select("*").eq("challenge_id", challenge_id).execute()
        return resp.data or []

    async def get_open_attempt(self, challenge_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        client = await get_supabase()
        resp = (
            client.table("challenge_attempts")
            .select("*")
            .eq("challenge_id", challenge_id)
            .eq("user_id", user_id)
            .eq("status", "open")
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]
        return None

    async def start_attempt(self, challenge_id: str, user_id: str) -> Dict[str, Any]:
        client = await get_supabase()
        resp = client.table("challenge_attempts").insert({
            "challenge_id": challenge_id,
            "user_id": user_id,
            "status": "open",
        }).execute()
        if not resp.data:
            raise RuntimeError("Failed to start challenge attempt")
        return resp.data[0]

    async def finalize_attempt(self, attempt_id: str, score: int, correct_count: int) -> Dict[str, Any]:
        client = await get_supabase()
        resp = (
            client.table("challenge_attempts")
            .update({
                "score": score,
                "correct_count": correct_count,
                "status": "completed",
                "submitted_at": "now()",
            })
            .eq("id", attempt_id)
            .execute()
        )
        if not resp.data:
            raise RuntimeError("Failed to finalize challenge attempt")
        return resp.data[0]

challenge_repository = ChallengeRepository()
