from typing import List
from app.DB.supabase import get_supabase
from app.features.students import repository, repository_analytics
from app.features.students.models import StudentProfileUpdate, StudentProfile
from app.features.students.schemas import StudentProfile, ModuleProgress, BadgeInfo,StudentProfileUpdate

# -------------------
# Profile
# -------------------
async def get_student_profile(user_id: int) -> StudentProfile:
    data = await repository.get_student_profile(user_id)
    if not data:
        raise ValueError(f"Student with id={user_id} not found")
    return data  

ALLOWED_COLUMNS = ["email", "full_name", "avatar_url", "phone", "bio"]

async def update_student_profile(user_id: int, profile_data: StudentProfileUpdate):
    client = await get_supabase()
    
    # Only include fields that are set and allowed
    update_dict = {
        k: v for k, v in profile_data.dict(exclude_unset=True).items()
        if k in ALLOWED_COLUMNS
    }

    if not update_dict:
        return {"message": "No valid fields provided for update."}

    # Update the fields in the DB
    await client.table("profiles").update(update_dict).eq("id", user_id).execute()

    # Fetch the updated record to return full profile
    updated_record = await client.table("profiles").select("*").eq("id", user_id).single().execute()

    return updated_record.data

# -------------------
# Modules
# -------------------
async def get_student_modules(user_id: int) -> List[ModuleProgress]:
    modules_data = await repository.get_student_modules(user_id)
    return modules_data  # don't wrap with ModuleProgress(**m)

    modules_data = await repository.get_student_modules(user_id)
    return [ModuleProgress(**m) for m in modules_data]

# -------------------
# Badges
# -------------------
async def get_student_badges(user_id: int) -> List[BadgeInfo]:
    badges_data = await repository.get_student_badges(user_id)
    return [
        BadgeInfo(
            id=b["id"],
            name=b.get("name", ""),
            badge_type=b.get("badge_type", ""),
            awarded_at=b["awarded_at"]
        )
        for b in badges_data
    ]
