from __future__ import annotations
from typing import Dict, Any, List
from app.DB.supabase import get_supabase

class ChallengeRepository:
    """Repository for challenge creation operations only"""
    
    async def create_challenge(self, challenge_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new challenge record."""
        client = await get_supabase()
        resp = client.table("challenges").insert(challenge_data).execute()
        if not resp.data:
            raise RuntimeError("Failed to create challenge")
        return resp.data[0]

    async def list_challenges(self) -> List[Dict[str, Any]]:
        """List all challenges."""
        client = await get_supabase()
        resp = client.table("challenges").select("*").execute()
        return resp.data or []

    async def get_challenges_by_week(self, week_number: int) -> List[Dict[str, Any]]:
        """Get all challenges for a specific week."""
        client = await get_supabase()
        resp = client.table("challenges").select("*").eq("week_number", week_number).execute()
        return resp.data or []

    async def publish_week_challenges(self, week_number: int) -> Dict[str, Any]:
        """Publish all challenges for a specific week (change status from draft to active)."""
        client = await get_supabase()
        resp = (
            client.table("challenges")
            .update({"status": "active"})
            .eq("week_number", week_number)
            .eq("status", "draft")
            .execute()
        )
        return {"updated_count": len(resp.data or []), "challenges": resp.data or []}

challenge_repository = ChallengeRepository()
