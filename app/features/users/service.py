
"""User service layer (Supabase-backed)."""

from typing import Optional, List, Dict, Any
from .repository import user_repository
from .schemas import UserCreate, UserUpdate, UserRoleUpdate, User
from .normalization import normalize_user, maybe_normalize_user


async def ensure_user_provisioned(supabase_id: str, email: str, full_name: Optional[str] = None) -> Dict[str, Any]:
    """Idempotently ensure a user row exists for the given Supabase auth user."""
    user = await user_repository.get_user_by_supabase_id(supabase_id)
    if user:
        return user
    if not user:
        existing_email = await user_repository.get_user_by_email(email)
        if existing_email:
            if not existing_email.get("supabase_id"):
                await user_repository.update_user(existing_email["id"], {"supabase_id": supabase_id})
            return existing_email
    uc = UserCreate(email=email, password="", full_name=full_name)
    return await user_repository.create_user(supabase_id, uc)


async def list_users(offset: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
    return await user_repository.list_users(offset, limit)


async def create_user(supabase_id: str, user_data: UserCreate) -> Dict[str, Any]:
    return await user_repository.create_user(supabase_id, user_data)


async def get_user_by_supabase_id(supabase_id: str) -> Optional[Dict[str, Any]]:
    return await user_repository.get_user_by_supabase_id(supabase_id)


async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    return await user_repository.get_user_by_email(email)


async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    return await user_repository.get_user_by_id(user_id)

# Convenience typed helpers
async def get_user_schema_by_id(user_id: str) -> Optional[User]:
    return maybe_normalize_user(await get_user_by_id(user_id))

async def get_user_schema_by_supabase_id(supabase_id: str) -> Optional[User]:
    return maybe_normalize_user(await get_user_by_supabase_id(supabase_id))


async def update_user(user_id: str, user_data: UserUpdate) -> Optional[Dict[str, Any]]:
    update_fields = {k: v for k, v in user_data.model_dump(exclude_unset=True).items() if v is not None}
    return await user_repository.update_user(user_id, update_fields)


async def update_user_role(user_id: str, role_data: UserRoleUpdate) -> Optional[Dict[str, Any]]:
    return await user_repository.update_user(user_id, {"role": role_data.role})


async def update_user_last_signin(user_id: str) -> bool:
    return await user_repository.update_last_sign_in(user_id)


async def delete_user(user_id: str) -> bool:
    return await user_repository.delete_user(user_id)

