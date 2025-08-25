from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from app.db.supabase import get_supabase
from .schemas import ProfileCreate, ProfileUpdate

class ProfileRepository:
    async def create_profile(self, supabase_id: str, data: ProfileCreate) -> dict:
        client = await get_supabase()
        record = {
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
        resp = await client.table("profiles").insert(record).execute()
        if not getattr(resp, "data", None):
            raise RuntimeError("Failed to create profile record")
        return resp.data[0]

    async def get_by_id(self, profile_id: str) -> Optional[dict]:
        client = await get_supabase()
        resp = await client.table("profiles").select("*").eq("id", profile_id).execute()
        data = getattr(resp, "data", None)
        if not data:
            return None
        return data[0] if isinstance(data, list) else data

    async def get_by_supabase_id(self, supabase_id: str) -> Optional[dict]:
        client = await get_supabase()
        resp = await client.table("profiles").select("*").eq("supabase_id", supabase_id).execute()
        data = getattr(resp, "data", None)
        if not data:
            return None
        return data[0] if isinstance(data, list) else data

    async def get_by_email(self, email: str) -> Optional[dict]:
        client = await get_supabase()
        resp = await client.table("profiles").select("*").eq("email", email).execute()
        data = getattr(resp, "data", None)
        if not data:
            return None
        return data[0] if isinstance(data, list) else data

    async def list_profiles(self, offset: int = 0, limit: int = 50) -> List[dict]:
        client = await get_supabase()
        resp = await (client.table("profiles").select("*").order("created_at", desc=True).range(offset, offset + max(limit,1) - 1).execute())
        return resp.data or []

    async def update_profile(self, profile_id: str, fields: Dict[str, Any]) -> Optional[dict]:
        if not fields:
            return await self.get_by_id(profile_id)
        client = await get_supabase()
        resp = await client.table("profiles").update(fields).eq("id", profile_id).execute()
        return resp.data[0] if getattr(resp, "data", None) else None

    async def update_last_sign_in(self, profile_id: str) -> bool:
        client = await get_supabase()
        now_iso = datetime.now(timezone.utc).isoformat()
        resp = await client.table("profiles").update({"last_sign_in": now_iso}).eq("id", profile_id).execute()
        return bool(getattr(resp, "data", None))

    async def delete_profile(self, profile_id: str) -> bool:
        client = await get_supabase()
        resp = await client.table("profiles").delete().eq("id", profile_id).execute()
        return bool(getattr(resp, "data", None) or getattr(resp, "count", None))

profile_repository = ProfileRepository()
