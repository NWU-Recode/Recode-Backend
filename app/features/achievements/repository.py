#this is all ai - to use as starting point because i dont understand this part yet (:
from __future__ import annotations
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
from app.DB.supabase import get_supabase

class AchievementsRepository:
    #badges
    async def get_badges_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        client = await get_supabase()
        resp = (
            client.table("user_badges")
            .select("*, badges(*)")
            .eq("user_id", user_id)
            .execute()
        )
        return resp.data or []

    async def add_badge_to_user(self, user_id: str, badge_id: str) -> Dict[str, Any]:
        client = await get_supabase()
        resp = client.table("user_badges").insert({"user_id": user_id, "badge_id": badge_id}).execute()
        if not resp.data:
            raise RuntimeError("Failed to add badge to user")
        return resp.data[0]

    async def add_badges_batch(self, user_id: str, badge_ids: List[str]) -> List[Dict[str, Any]]:
        client = await get_supabase()
        data = [{"user_id": user_id, "badge_id": b} for b in badge_ids]
        resp = client.table("user_badges").insert(data).execute()
        return resp.data or []

    #titles
    async def get_title_for_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        client = await get_supabase()
        resp = (
            client.table("user_titles")
            .select("*, titles(*)")
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        return resp.data or None

    async def award_title(self, user_id: str, title_id: str) -> Dict[str, Any]:
        client = await get_supabase()
        resp = client.table("user_titles").insert({"user_id": user_id, "title_id": title_id}).execute()
        if not resp.data:
            raise RuntimeError("Failed to award title to user")
        return resp.data[0]
    
    #elo
    async def get_user_elo(self, user_id: str) -> Optional[Dict[str, Any]]:
        client = await get_supabase()
        resp = client.table("user_elo").select("*").eq("user_id", user_id).single().execute()
        return resp.data or None

    async def update_user_elo(self, user_id: str, new_elo: int) -> Dict[str, Any]:
        client = await get_supabase()
        resp = client.table("user_elo").update({"elo": new_elo}).eq("user_id", user_id).execute()
        if not resp.data:
            raise RuntimeError("Failed to update user Elo")
        return resp.data[0]

    #achievements aggregate
    async def get_achievements_for_user(self, user_id: str) -> Dict[str, Any]:
        badges = await self.get_badges_for_user(user_id)
        title = await self.get_title_for_user(user_id)
        elo = await self.get_user_elo(user_id)
        return {
            "elo": elo["elo"] if elo else 0,
            "badges": badges,
            "title": title,
        }

achievements_repository = AchievementsRepository()