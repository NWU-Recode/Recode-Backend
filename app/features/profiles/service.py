from typing import Optional, List, Dict, Any
from .repository import profile_repository
from .schemas import ProfileCreate, ProfileUpdate, ProfileRoleUpdate, Profile

async def ensure_profile_provisioned(supabase_id: str, email: str, full_name: Optional[str] = None) -> Dict[str, Any]:
    prof = await profile_repository.get_by_supabase_id(supabase_id)
    if prof:
        return prof
    existing_email = await profile_repository.get_by_email(email)
    if existing_email:
        if not existing_email.get("supabase_id"):
            await profile_repository.update_profile(existing_email["id"], {"supabase_id": supabase_id})
        return existing_email
    pc = ProfileCreate(email=email, password="", full_name=full_name)
    return await profile_repository.create_profile(supabase_id, pc)

async def list_profiles(offset: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
    return await profile_repository.list_profiles(offset, limit)

async def create_profile(supabase_id: str, data: ProfileCreate) -> Dict[str, Any]:
    return await profile_repository.create_profile(supabase_id, data)

async def get_profile_by_supabase_id(supabase_id: str) -> Optional[Dict[str, Any]]:
    return await profile_repository.get_by_supabase_id(supabase_id)

async def get_profile_by_email(email: str) -> Optional[Dict[str, Any]]:
    return await profile_repository.get_by_email(email)

async def get_profile_by_id(profile_id: int) -> Optional[Dict[str, Any]]:
    return await profile_repository.get_by_id(profile_id)

async def update_profile(profile_id: int, data: ProfileUpdate) -> Optional[Dict[str, Any]]:
    fields = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    return await profile_repository.update_profile(profile_id, fields)

async def update_profile_role(profile_id: int, role_data: ProfileRoleUpdate) -> Optional[Dict[str, Any]]:
    return await profile_repository.update_profile(profile_id, {"role": role_data.role})

async def update_profile_last_signin(profile_id: int) -> bool:
    return await profile_repository.update_last_sign_in(profile_id)

async def delete_profile(profile_id: int) -> bool:
    return await profile_repository.delete_profile(profile_id)

