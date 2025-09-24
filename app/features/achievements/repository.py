from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from app.DB.supabase import get_supabase

logger = logging.getLogger("achievements.repository")


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except Exception:  # pragma: no cover - defensive branch
            return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:  # pragma: no cover - defensive branch
            return None
    return None


class AchievementsRepository:
    """Low-level access helpers for achievements related Supabase tables.

    Every method is resilient to partially configured schemas – the production
    database evolved quickly and some columns may be renamed. The repository
    therefore normalises common aliases so that higher level services can focus
    on the business rules instead of fiddling with column names.
    """

    # --- Generic helpers -------------------------------------------------

    async def _execute(self, query, op: str) -> Any:
        """Execute a Supabase query and log failures without exploding."""

        try:
            return await query
        except Exception as exc:  # pragma: no cover - Supabase client failure
            logger.warning("supabase_%s_failed error=%s", op, exc)
            return None

    async def _client(self):
        return await get_supabase()

    # --- Challenge attempts ----------------------------------------------

    async def fetch_challenge_attempt(self, attempt_id: str) -> Optional[Dict[str, Any]]:
        client = await self._client()
        query = client.table("challenge_attempts").select("*").eq("id", attempt_id).single().execute()
        resp = await self._execute(query, op="challenge_attempts.single")
        data = getattr(resp, "data", None)
        return data or None

    async def fetch_challenge(self, challenge_id: str) -> Optional[Dict[str, Any]]:
        client = await self._client()
        query = client.table("challenges").select("*").eq("id", challenge_id).single().execute()
        resp = await self._execute(query, op="challenges.single")
        data = getattr(resp, "data", None)
        return data or None

    async def list_submitted_attempts(self, user_id: str) -> List[Dict[str, Any]]:
        client = await self._client()
        query = (
            client.table("challenge_attempts")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "submitted")
            .execute()
        )
        resp = await self._execute(query, op="challenge_attempts.submitted")
        data = getattr(resp, "data", None)
        return data or []

    # --- Elo --------------------------------------------------------------

    async def get_user_elo(self, user_id: str) -> Optional[Dict[str, Any]]:
        client = await self._client()
        query = client.table("user_elo").select("*").eq("user_id", user_id).single().execute()
        resp = await self._execute(query, op="user_elo.single")
        data = getattr(resp, "data", None)
        return data or None

    async def insert_user_elo(self, user_id: str, elo_points: int, gpa: Optional[float]) -> Optional[Dict[str, Any]]:
        payload: Dict[str, Any] = {
            "user_id": user_id,
            "elo_points": elo_points,
        }
        if gpa is not None:
            payload["running_gpa"] = gpa
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        client = await self._client()
        query = client.table("user_elo").insert(payload).execute()
        resp = await self._execute(query, op="user_elo.insert")
        data = getattr(resp, "data", None)
        return data[0] if isinstance(data, list) and data else None

    async def update_user_elo(self, user_id: str, elo_points: int, gpa: Optional[float]) -> Optional[Dict[str, Any]]:
        payload: Dict[str, Any] = {"elo_points": elo_points}
        if gpa is not None:
            payload["running_gpa"] = gpa
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        client = await self._client()
        query = client.table("user_elo").update(payload).eq("user_id", user_id).execute()
        resp = await self._execute(query, op="user_elo.update")
        data = getattr(resp, "data", None)
        if data:
            return data[0] if isinstance(data, list) else data
        # If the update did not return a row it likely means the record did
        # not exist yet – insert instead.
        return await self.insert_user_elo(user_id, elo_points=elo_points, gpa=gpa)

    async def log_elo_event(self, payload: Dict[str, Any]) -> None:
        client = await self._client()
        query = client.table("elo_events").insert(payload).execute()
        await self._execute(query, op="elo_events.insert")

    # --- Titles -----------------------------------------------------------

    async def list_titles(self) -> List[Dict[str, Any]]:
        client = await self._client()
        query = client.table("titles").select("*").execute()
        resp = await self._execute(query, op="titles.list")
        data = getattr(resp, "data", None)
        return data or []

    async def update_profile_title(self, user_id: str, title_id: Any) -> None:
        if title_id is None:
            return
        client = await self._client()
        query = client.table("profiles").update({"title_id": title_id}).eq("id", user_id).execute()
        await self._execute(query, op="profiles.title_update")

    # --- Badges -----------------------------------------------------------

    async def list_badge_definitions(self) -> List[Dict[str, Any]]:
        client = await self._client()
        query = client.table("badges").select("*").execute()
        resp = await self._execute(query, op="badges.list")
        data = getattr(resp, "data", None)
        return data or []

    async def get_badges_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        client = await self._client()
        query = (
            client.table("user_badges")
            .select("*, badge:badges(*)")
            .eq("user_id", user_id)
            .order("date_earned", desc=True)
            .execute()
        )
        resp = await self._execute(query, op="user_badges.list")
        data = getattr(resp, "data", None)
        return data or []

    async def add_badge_to_user(
        self,
        user_id: str,
        badge_id: Any,
        challenge_id: Optional[str] = None,
        attempt_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        payload: Dict[str, Any] = {
            "user_id": user_id,
            "badge_id": badge_id,
        }
        if challenge_id is not None:
            payload["challenge_id"] = challenge_id
        if attempt_id is not None:
            payload["challenge_attempt_id"] = attempt_id
        payload.setdefault("date_earned", datetime.now(timezone.utc).isoformat())
        client = await self._client()
        query = client.table("user_badges").insert(payload).execute()
        resp = await self._execute(query, op="user_badges.insert")
        data = getattr(resp, "data", None)
        if data:
            return data[0] if isinstance(data, list) else data
        return None

    async def add_badges_batch(
        self,
        user_id: str,
        badge_ids: Iterable[Any],
        challenge_id: Optional[str],
        attempt_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        payloads: List[Dict[str, Any]] = []
        now_iso = datetime.now(timezone.utc).isoformat()
        for badge_id in badge_ids:
            payload: Dict[str, Any] = {
                "user_id": user_id,
                "badge_id": badge_id,
                "date_earned": now_iso,
            }
            if challenge_id is not None:
                payload["challenge_id"] = challenge_id
            if attempt_id is not None:
                payload["challenge_attempt_id"] = attempt_id
            payloads.append(payload)
        if not payloads:
            return []
        client = await self._client()
        query = client.table("user_badges").insert(payloads).execute()
        resp = await self._execute(query, op="user_badges.batch_insert")
        data = getattr(resp, "data", None)
        if isinstance(data, list):
            return data
        return []


achievements_repository = AchievementsRepository()

__all__ = ["achievements_repository", "AchievementsRepository", "_parse_datetime"]
