from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from app.DB.supabase import get_supabase
from .schemas import ProfileCreate, ProfileUpdate
import logging
import asyncio, time, os
from app.common import cache

logger = logging.getLogger("profiles.repository")

class ProfileRepository:
    async def _exec(self, awaitable, op: str):
        timeout = float(os.getenv("SUPABASE_QUERY_TIMEOUT", "5"))
        t0 = time.perf_counter()
        try:
            resp = await asyncio.wait_for(awaitable, timeout=timeout)
            ms = int((time.perf_counter() - t0) * 1000)
            if ms > 50:
                logger.info("supabase_%s_ms=%d", op, ms)
            return resp
        except asyncio.TimeoutError:
            raise RuntimeError(f"Supabase {op} timed out after {timeout}s")

    async def create_profile(self, supabase_id: str, data: ProfileCreate) -> dict:
        client = await get_supabase()
        record = {
            # If student_number provided (provision after binding step), set as id; else let DB default/ fail fast if required
            **({"id": data.student_number} if getattr(data, "student_number", None) else {}),
            "supabase_id": supabase_id,
            "email": data.email,
            "full_name": data.full_name,
            "avatar_url": getattr(data, "avatar_url", None),
            "phone": getattr(data, "phone", None),
            "bio": getattr(data, "bio", None),
            "role": "student",
            "is_active": True,
            "is_superuser": False,
            "email_verified": False,
            "user_metadata": {},
        }
        resp = await self._exec(client.table("profiles").insert(record).execute(), op="profiles.insert")
        if not getattr(resp, "data", None):
            raise RuntimeError("Failed to create profile record")
        return resp.data[0]

    async def get_by_id(self, profile_id: int) -> Optional[dict]:
        key = f"profiles:id:{profile_id}"
        cached = cache.get(key)
        if cached is not None:
            return cached
        client = await get_supabase()
        resp = await self._exec(client.table("profiles").select("*").eq("id", profile_id).execute(), op="profiles.select_by_id")
        data = getattr(resp, "data", None)
        if not data:
            return None
        value = data[0] if isinstance(data, list) else data
        cache.set(key, value)
        return value

    async def get_by_supabase_id(self, supabase_id: str) -> Optional[dict]:
        key = f"profiles:sid:{supabase_id}"
        cached = cache.get(key)
        if cached is not None:
            return cached
        client = await get_supabase()
        resp = await self._exec(client.table("profiles").select("*").eq("supabase_id", supabase_id).execute(), op="profiles.select_by_supabase_id")
        data = getattr(resp, "data", None)
        if not data:
            return None
        value = data[0] if isinstance(data, list) else data
        cache.set(key, value)
        return value

    async def get_by_email(self, email: str) -> Optional[dict]:
        key = f"profiles:email:{email.lower()}"
        cached = cache.get(key)
        if cached is not None:
            return cached
        client = await get_supabase()
        resp = await self._exec(client.table("profiles").select("*").eq("email", email).execute(), op="profiles.select_by_email")
        data = getattr(resp, "data", None)
        if not data:
            return None
        value = data[0] if isinstance(data, list) else data
        cache.set(key, value)
        return value

    async def list_profiles(self, offset: int = 0, limit: int = 50) -> List[dict]:
        client = await get_supabase()
        try:
            key = f"profiles:list:{offset}:{limit}"
            cached = cache.get(key)
            if cached is not None:
                return cached
            resp = await self._exec(
                client.table("profiles")
                .select("*")
                .order("created_at", desc=True)
                .range(offset, offset + max(limit, 1) - 1)
                .execute(),
                op="profiles.list",
            )
            value = resp.data or []
            cache.set(key, value)
            return value
        except Exception as e:
            logger.error("Error fetching profiles: %s", str(e))
            return []

    async def update_profile(self, profile_id: int, fields: Dict[str, Any]) -> Optional[dict]:
        if not fields:
            return await self.get_by_id(profile_id)
        client = await get_supabase()
        resp = await self._exec(client.table("profiles").update(fields).eq("id", profile_id).execute(), op="profiles.update")
        return resp.data[0] if getattr(resp, "data", None) else None

    async def update_last_sign_in(self, profile_id: int) -> bool:
        client = await get_supabase()
        now_iso = datetime.now(timezone.utc).isoformat()
        resp = await self._exec(client.table("profiles").update({"last_sign_in": now_iso}).eq("id", profile_id).execute(), op="profiles.update_last_sign_in")
        return bool(getattr(resp, "data", None))

    async def delete_profile(self, profile_id: int) -> bool:
        client = await get_supabase()
        resp = await self._exec(client.table("profiles").delete().eq("id", profile_id).execute(), op="profiles.delete")
        return bool(getattr(resp, "data", None) or getattr(resp, "count", None))

    # Removed legacy student_number binding methods; now handled in DB trigger via auth user metadata.

profile_repository = ProfileRepository()
