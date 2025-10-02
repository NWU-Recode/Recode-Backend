from app.DB.supabase import get_supabase
from typing import List
from app.features.students.schemas import StudentProfile, ModuleProgress

async def get_student_profile(user_id: int) -> dict:
    client = await get_supabase()
    resp = await client.table("profiles").select("*, titles(name)").eq("id", user_id).single().execute()
    data = resp.data
    if data:
            if data.get("titles"):
                data["title_name"] = data["titles"]["name"]
                del data["titles"]  # Remove nested object
            
            # Remove title_id since frontend doesn't need it
            data.pop("title_id", None)
    return data

async def get_student_modules(user_id: int) -> List[ModuleProgress]:
    client = await get_supabase()

    # Step 1: Get enrolments for this student
    enrolments_resp = await client.table("enrolments").select("module_id").eq("student_id", user_id).execute()
    module_ids = [row["module_id"] for row in enrolments_resp.data or []]

    # Step 2: Fetch module metadata for each module_id
    modules = []
    for module_id in module_ids:
        mod_resp = await client.table("modules").select("id, code, name").eq("id", module_id).single().execute()
        if mod_resp and mod_resp.data:
            mod = mod_resp.data
            modules.append(ModuleProgress(
                module_id=mod["id"],
                module_code=mod["code"],
                module_name=mod["name"],
                progress_percent=0.0  # default until you compute actual progress
            ))

    return modules



async def get_student_badges(user_id: int) -> list[dict]:
    client = await get_supabase()
    badge_rows = await client.table("user_badge").select("badge_id, awarded_at").eq("profile_id", user_id).execute()
    badges = []
    for row in badge_rows.data or []:
        badge_meta = await client.table("badges").select("*").eq("id", row["badge_id"]).single().execute()
        if badge_meta.data:
            badges.append({
                "id": row["badge_id"],
                "name": badge_meta.data["name"],
                "description": badge_meta.data.get("description"),
                "badge_type": badge_meta.data["badge_type"],
                "awarded_at": row["awarded_at"]
            })
    return badges
