from __future__ import annotations
import logging
from datetime import datetime, timezone, date
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

    async def list_attempts_for_challenge(self, challenge_id: str) -> List[Dict[str, Any]]:
        client = await self._client()
        query = (
            client.table("challenge_attempts")
            .select("*")
            .eq("challenge_id", challenge_id)
            .eq("status", "submitted")
            .execute()
        )
        resp = await self._execute(query, op="challenge_attempts.by_challenge")
        data = getattr(resp, "data", None)
        return data or []

    # --- Elo --------------------------------------------------------------

    async def get_user_elo(
        self,
        user_id: str,
        module_code: Optional[str] = None,
        semester_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        client = await self._client()
        if module_code is None and semester_id is None:
            query = (
                client.table("user_elo")
                .select("*")
                .eq("user_id", user_id)
                .order("updated_at", desc=True)
                .limit(1)
            )
            resp = await self._execute(query.execute(), op="user_elo.latest")
            data = getattr(resp, "data", None)
            if isinstance(data, list):
                return data[0] if data else None
            if isinstance(data, dict):
                return data
            return None

        query = client.table("user_elo").select("*").eq("user_id", user_id)
        if module_code is not None:
            query = query.eq("module_code", module_code)
        if semester_id is not None:
            query = query.eq("semester_id", semester_id)
        resp = await self._execute(query.maybe_single().execute(), op="user_elo.scoped")
        data = getattr(resp, "data", None)
        if isinstance(data, list):
            return data[0] if data else None
        return data or None

    async def insert_user_elo(
        self,
        user_id: str,
        elo_points: int,
        gpa: Optional[float],
        module_code: Optional[str] = None,
        semester_id: Optional[str] = None,
        semester_start: Optional[date] = None,
        semester_end: Optional[date] = None,
    ) -> Optional[Dict[str, Any]]:
        payload: Dict[str, Any] = {
            "user_id": user_id,
            "elo_points": elo_points,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if gpa is not None:
            payload["running_gpa"] = gpa
        optional_fields: Dict[str, Any] = {}
        if module_code is not None:
            optional_fields["module_code"] = module_code
        if semester_id is not None:
            optional_fields["semester_id"] = semester_id
        if semester_start is not None:
            optional_fields["semester_start"] = semester_start.isoformat()
        if semester_end is not None:
            optional_fields["semester_end"] = semester_end.isoformat()
        payload.update(optional_fields)
        client = await self._client()
        resp = await self._execute(client.table("user_elo").insert(payload).execute(), op="user_elo.insert")
        data = getattr(resp, "data", None)
        if not data and optional_fields:
            fallback_payload: Dict[str, Any] = {
                "user_id": user_id,
                "elo_points": elo_points,
                "updated_at": payload["updated_at"],
            }
            if gpa is not None:
                fallback_payload["running_gpa"] = gpa
            resp = await self._execute(
                client.table("user_elo").insert(fallback_payload).execute(),
                op="user_elo.insert_fallback",
            )
            data = getattr(resp, "data", None)
        if isinstance(data, list):
            return data[0] if data else None
        return data or None

    async def update_user_elo(
        self,
        user_id: str,
        elo_points: int,
        gpa: Optional[float],
        module_code: Optional[str] = None,
        semester_id: Optional[str] = None,
        semester_start: Optional[date] = None,
        semester_end: Optional[date] = None,
    ) -> Optional[Dict[str, Any]]:
        payload: Dict[str, Any] = {
            "elo_points": elo_points,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if gpa is not None:
            payload["running_gpa"] = gpa
        if module_code is not None:
            payload.setdefault("module_code", module_code)
        if semester_id is not None:
            payload.setdefault("semester_id", semester_id)
        if semester_start is not None:
            payload.setdefault("semester_start", semester_start.isoformat())
        if semester_end is not None:
            payload.setdefault("semester_end", semester_end.isoformat())
        client = await self._client()
        query = client.table("user_elo").update(payload).eq("user_id", user_id)
        if module_code is not None:
            query = query.eq("module_code", module_code)
        if semester_id is not None:
            query = query.eq("semester_id", semester_id)
        resp = await self._execute(query.execute(), op="user_elo.update")
        data = getattr(resp, "data", None)
        if isinstance(data, list) and data:
            return data[0]
        if isinstance(data, dict) and data:
            return data
        return await self.insert_user_elo(
            user_id,
            elo_points=elo_points,
            gpa=gpa,
            module_code=module_code,
            semester_id=semester_id,
            semester_start=semester_start,
            semester_end=semester_end,
        )

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
        # Some deployments use `user_badges` table, others `user_badge` - try both.
        for table_name in ("user_badges", "user_badge"):
            try:
                query = (
                    client.table(table_name)
                    .select("*, badge:badges(*)")
                    .eq("user_id", user_id)
                    .order("date_earned", desc=True)
                    .execute()
                )
            except Exception:
                continue
            resp = await self._execute(query, op=f"{table_name}.list")
            data = getattr(resp, "data", None)
            if data:
                # Normalize returned shape to always include badge key under `badge`
                normalized: List[Dict[str, Any]] = []
                for row in data:
                    if isinstance(row, dict):
                        # compatibility: some rows include `badges` or nested `badge`
                        if "badges" in row and "badge" not in row:
                            row["badge"] = row.get("badges")
                        normalized.append(row)
                return normalized
        return []

    async def add_badge_to_user(
        self,
        user_id: str,
        badge_id: Any,
        challenge_id: Optional[str] = None,
        attempt_id: Optional[str] = None,
        source_submission_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        payload: Dict[str, Any] = {
            "user_id": user_id,
            "badge_id": badge_id,
        }
        if challenge_id is not None:
            payload["challenge_id"] = challenge_id
        if attempt_id is not None:
            payload["challenge_attempt_id"] = attempt_id
        if source_submission_id is not None:
            payload["source_submission_id"] = source_submission_id
        ts = datetime.now(timezone.utc).isoformat()
        payload.setdefault("awarded_at", ts)
        payload.setdefault("date_earned", ts)
        client = await self._client()
        # Try inserting into either user_badges or user_badge depending on schema
        for table_name in ("user_badges", "user_badge"):
            try:
                query = client.table(table_name).insert(payload).execute()
            except Exception:
                continue
            resp = await self._execute(query, op=f"{table_name}.insert")
            data = getattr(resp, "data", None)
            if data:
                return data[0] if isinstance(data, list) else data
        return None
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
        source_submission_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        payloads: List[Dict[str, Any]] = []
        now_iso = datetime.now(timezone.utc).isoformat()
        for badge_id in badge_ids:
            payload: Dict[str, Any] = {
                "user_id": user_id,
                "badge_id": badge_id,
                "date_earned": now_iso,
                "awarded_at": now_iso,
            }
            if challenge_id is not None:
                payload["challenge_id"] = challenge_id
            if attempt_id is not None:
                payload["challenge_attempt_id"] = attempt_id
            if source_submission_id is not None:
                payload["source_submission_id"] = source_submission_id
            payloads.append(payload)
        if not payloads:
            return []
        client = await self._client()
        # Try batch insert into both possible table names
        for table_name in ("user_badges", "user_badge"):
            try:
                query = client.table(table_name).insert(payloads).execute()
            except Exception:
                continue
            resp = await self._execute(query, op=f"{table_name}.batch_insert")
            data = getattr(resp, "data", None)
            if isinstance(data, list) and data:
                return data
        # Fallback: try inserting one-by-one
        inserted: List[Dict[str, Any]] = []
        for p in payloads:
            row = await self.add_badge_to_user(
                p.get("user_id"), p.get("badge_id"), p.get("challenge_id"), p.get("challenge_attempt_id"), p.get("source_submission_id")
            )
            if row:
                inserted.append(row)
        return inserted


achievements_repository = AchievementsRepository()

__all__ = ["achievements_repository", "AchievementsRepository", "_parse_datetime"]
