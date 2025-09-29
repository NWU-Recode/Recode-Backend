from app.DB.supabase import get_supabase

async def fetch_submissions(user_id: int) -> list[dict]:
    client = await get_supabase()
    resp = await client.table("code_submissions").select("*").eq("user_id", user_id).execute()
    return resp.data or []

async def fetch_code_submissions(user_id: int) -> list[dict]:
    client = await get_supabase()
    resp = await client.table("code_submissions").select("*").eq("user_id", user_id).execute()
    return resp.data or []

async def fetch_user_elo(user_id: int) -> dict:
    client = await get_supabase()
    resp = await client.table("user_elo").select("*").eq("student_id", user_id).maybe_single().execute()
    if not resp or not resp.data:
        print(f"[WARN] No ELO data found for student_id={user_id}")
    return getattr(resp, "data", {}) or {}




async def fetch_student_analytics(user_id: int) -> dict:
    submissions = await fetch_submissions(user_id)
    code_subs = await fetch_code_submissions(user_id)
    return {
        "total_attempts": len(submissions),
        "total_passed": sum(1 for s in code_subs if s.get("is_correct")),
        "total_failed": len(submissions) - sum(1 for s in code_subs if s.get("is_correct")),
        "recent": submissions[:5]
    }
