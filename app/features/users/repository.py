from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from app.DB.client import get_supabase
from .schemas import UserCreate, UserUpdate


class UserRepository:
    """Supabase (PostgREST) based async repository for users."""

    async def create_user(self, supabase_id: str, user_data: UserCreate) -> dict:
        client = await get_supabase()
        record = {
            "supabase_id": supabase_id,
            "email": user_data.email,
            "full_name": user_data.full_name,
            "avatar_url": getattr(user_data, "avatar_url", None),
            "phone": getattr(user_data, "phone", None),
            "bio": getattr(user_data, "bio", None),
            "role": "student",
            "is_active": True,
            "is_superuser": False,
            "email_verified": False,
            "user_metadata": {},
        }
        resp = client.table("users").insert(record).execute()
        if not resp.data:
            raise RuntimeError("Failed to create user record")
        return resp.data[0]

    async def get_user_by_id(self, user_id: str) -> Optional[dict]:
        client = await get_supabase()
        resp = client.table("users").select("*").eq("id", user_id).single().execute()
        return resp.data or None

    async def get_user_by_supabase_id(self, supabase_id: str) -> Optional[dict]:
        client = await get_supabase()
        resp = client.table("users").select("*").eq("supabase_id", supabase_id).single().execute()
        return resp.data or None

    async def get_user_by_email(self, email: str) -> Optional[dict]:
        client = await get_supabase()
        resp = client.table("users").select("*").eq("email", email).single().execute()
        return resp.data or None

    async def list_users(self, offset: int = 0, limit: int = 50) -> List[dict]:
        client = await get_supabase()
        resp = (
            client.table("users")
            .select("*")
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return resp.data or []

    async def update_user(self, user_id: str, update_fields: Dict[str, Any]) -> Optional[dict]:
        if not update_fields:
            return await self.get_user_by_id(user_id)
        client = await get_supabase()
        resp = client.table("users").update(update_fields).eq("id", user_id).execute()
        return resp.data[0] if resp.data else None

    async def update_supabase_id(self, user_id: str, new_supabase_id: str) -> bool:
        client = await get_supabase()
        resp = client.table("users").update({"supabase_id": new_supabase_id}).eq("id", user_id).execute()
        return bool(resp.data)

    async def update_last_sign_in(self, user_id: str) -> bool:
        client = await get_supabase()
        now_iso = datetime.now(timezone.utc).isoformat()
        resp = client.table("users").update({"last_sign_in": now_iso}).eq("id", user_id).execute()
        return bool(resp.data)

    async def delete_user(self, user_id: str) -> bool:
        client = await get_supabase()
        resp = client.table("users").delete().eq("id", user_id).execute()
        return bool(getattr(resp, "count", None))

user_repository = UserRepository()
