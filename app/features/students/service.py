from app.DB.supabase import get_supabase
from app.features.students import repository
from app.features.students.schemas import (
    StudentProfile,
    StudentProfileUpdate,
    ModuleProgress,
    BadgeInfo,
)

ALLOWED_COLUMNS = ["email", "full_name", "avatar_url", "phone", "bio"]

async def get_student_profile(user_id: int) -> StudentProfile:
    return await repository.get_student_profile(user_id)

async def update_student_profile(user_id: int, update_data: StudentProfileUpdate) -> dict:
    client = await get_supabase()

    # Fetch current profile
    resp = await client.table("profiles").select("*").eq("id", user_id).single().execute()
    profile = resp.data or {}

    # Only update fields that are explicitly set
    patch = {}
    for field, value in update_data.dict(exclude_unset=True).items():
        # Skip placeholder values like "string"
        if value not in [None, "string", ""]:
            patch[field] = value

    # If nothing to update, return current profile
    if not patch:
        return profile

    # Apply patch
    update_resp = await client.table("profiles").update(patch).eq("id", user_id).execute()
    return update_resp.data[0] if update_resp.data else profile

async def get_student_modules(user_id: int) -> list[ModuleProgress]:
    raw_modules = await repository.get_student_modules(user_id)
    return raw_modules


async def get_student_badges(user_id: int) -> list[BadgeInfo]:
    raw_badges = await repository.get_student_badges(user_id)
    return [BadgeInfo(**b) for b in raw_badges]
