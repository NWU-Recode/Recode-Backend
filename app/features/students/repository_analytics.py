from typing import List
from app.DB.supabase import get_supabase

async def fetch_submissions(user_id: int) -> List[dict]:
    client = await get_supabase()
    resp = await client.table("code_submissions").select("*").eq("user_id", user_id).execute()
    return resp.data or []

async def fetch_code_submissions(user_id: int) -> List[dict]:
    client = await get_supabase()
    resp = await client.table("code_submissions").select("*").eq("user_id", user_id).execute()
    return resp.data or []

async def fetch_user_elo(user_id: int) -> dict:
    client = await get_supabase()
    resp = await client.table("user_elo").select("*").eq("student_id", user_id).single().execute()
    return resp.data or {}

async def fetch_challenge_topics(challenge_id: str) -> List[dict]:
    client = await get_supabase()
    resp = await client.table("challenge_topics").select("*").eq("challenge_id", challenge_id).execute()
    return resp.data or []

async def fetch_student_analytics(user_id: int) -> dict:
    # Fetch all student submissions
    submissions = await fetch_submissions(user_id)
    code_subs = await fetch_code_submissions(user_id)

    total_attempts = len(submissions)
    total_passed = sum(1 for s in code_subs if s.get("is_correct"))
    total_failed = total_attempts - total_passed

    # Optionally include recent submissions details
    return {
        "total_attempts": total_attempts,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "details": submissions
    }
