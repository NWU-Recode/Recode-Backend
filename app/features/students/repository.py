from typing import List
from app.DB.supabase import get_supabase
from .schemas import StudentProfile, ModuleProgress, BadgeInfo, TopicProgress, ChallengeProgress

# -------------------
# Profiles
# -------------------
async def get_student_profile(user_id: int) -> StudentProfile:
    client = await get_supabase()
    resp = await client.table("profiles").select("*").eq("id", user_id).single().execute()
    data = resp.data  
    if not data:
        return None
    return StudentProfile(
        id=data["id"],
        email=data["email"],
        full_name=data["full_name"],
        avatar_url=data.get("avatar_url"),
        bio=data.get("bio"),
        role=data["role"],
        is_active=data["is_active"],
        last_sign_in=data.get("last_sign_in")
    )

# -------------------
# Modules / Dashboard
# -------------------
async def get_student_modules(user_id: int) -> List[ModuleProgress]:
    client = await get_supabase()
    resp = await client.table("student_dashboard").select("*").eq("user_id", user_id).execute()
    rows = resp.data or []
    
    modules = [
        ModuleProgress(
            module_id=row["module_id"],
            module_code=row["module_code"],
            module_name=row["module_name"],
            elo=row["elo"],
            current_title=row.get("current_title"),
            current_streak=row.get("current_streak", 0),
            longest_streak=row.get("longest_streak", 0),
            total_points=row.get("total_points", 0),
            total_questions_passed=row.get("total_questions_passed", 0),
            challenges_completed=row.get("challenges_completed", 0),
            total_badges=row.get("total_badges", 0),
            last_submission=row.get("last_submission")
        )
        for row in rows
    ]
    return modules


# -------------------
# Badges
# -------------------
async def get_student_badges(user_id: int) -> list[BadgeInfo]:
    client = await get_supabase()
    
    # Step 1: Get user_badge rows
    resp = await client.table("user_badge").select("id, badge_id, awarded_at").eq("profile_id", user_id).execute()
    rows = resp.data or []
    
    badges = []
    for row in rows:
        # Step 2: Fetch badge metadata
        badge_resp = await client.table("badges").select("*").eq("id", row["badge_id"]).single().execute()
        badge_data = badge_resp.data
        if badge_data:
            badges.append(BadgeInfo(
                id=row["badge_id"],
                name=badge_data["name"],
                badge_type=badge_data["badge_type"],
                awarded_at=row["awarded_at"]
            ))
    return badges
