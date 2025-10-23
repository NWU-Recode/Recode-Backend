from app.DB.supabase import get_supabase
from collections import defaultdict

async def fetch_submissions(user_id: int) -> list[dict]:
    client = await get_supabase()
    resp = await client.table("code_submissions").select("*").eq("user_id", user_id).execute()
    return resp.data or []

async def fetch_code_results(user_id: int) -> list[dict]:
    client = await get_supabase()
    
    # Step 1: Get all submission IDs for this user
    subs_resp = await client.table("code_submissions").select("id").eq("user_id", user_id).execute()
    submission_ids = [s["id"] for s in subs_resp.data or []]

    if not submission_ids:
        return []  # No submissions, so no results

    # Step 2: Get code results for those submissions
    resp = await client.table("code_results") \
        .select("*") \
        .in_("submission_id", submission_ids) \
        .execute()
    
    return resp.data or []


async def fetch_challenge_attempts(user_id: int) -> list[dict]:
    client = await get_supabase()
    resp = await client.table("challenge_attempts").select("*").eq("user_id", user_id).execute()
    return resp.data or []

async def fetch_user_achievements(user_id: int) -> list[dict]:
    client = await get_supabase()
    resp = await client.table("user_badge").select("*").eq("profile_id", user_id).execute()
    return resp.data or []

async def fetch_elo_events(user_id: int) -> list[dict]:
    client = await get_supabase()
    resp = await client.table("elo_events").select("*").eq("student_id", user_id).execute()
    return resp.data or []

async def fetch_user_elo(user_id: int) -> dict:
    client = await get_supabase()
    resp = await client.table("user_elo").select("*").eq("student_id", user_id).single().execute()
    return resp.data or {}

async def fetch_question_progress(user_id: int) -> list[dict]:
    client = await get_supabase()
    resp = await client.table("user_question_progress").select("*").eq("profile_id", user_id).execute()
    return resp.data or []

from collections import defaultdict

async def fetch_student_analytics(user_id: int) -> dict:
    # Get all necessary data
    submissions = await fetch_submissions(user_id)
    code_results = await fetch_code_results(user_id)
    challenge_attempts = await fetch_challenge_attempts(user_id)
    achievements = await fetch_user_achievements(user_id)
    elo_events = await fetch_elo_events(user_id)
    user_elo = await fetch_user_elo(user_id)
    question_progress = await fetch_question_progress(user_id)

    # Compute totals per submission
    results_by_submission = defaultdict(list)
    for r in code_results:
        results_by_submission[r["submission_id"]].append(r)

    total_passed = sum(
        1 for results in results_by_submission.values() 
        if all(r.get("is_correct") for r in results)
    )
    total_attempts = len(submissions)
    total_failed = max(total_attempts - total_passed, 0)

    # Most recent 5 submissions (sorted by created_at if available)
    recent_submissions = sorted(
        submissions, 
        key=lambda s: s.get("created_at", ""),  
        reverse=True
    )[:5]

    # --- Compute per-challenge stats ---
    submissions_by_challenge = defaultdict(list)
    for s in submissions:
        submissions_by_challenge[s["challenge_id"]].append(s)

    challenge_stats = {}
    for challenge_id, subs in submissions_by_challenge.items():
        passed = 0
        for sub in subs:
            sub_results = results_by_submission.get(sub["id"], [])
            if sub_results and all(r.get("is_correct") for r in sub_results):
                passed += 1
        challenge_stats[challenge_id] = {
            "total_attempts": len(subs),
            "total_passed": passed,
            "total_failed": max(len(subs) - passed, 0)
        }

    # Build analytics dictionary
    analytics = {
        "total_attempts": total_attempts,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "recent_submissions": recent_submissions,
        "per_challenge_stats": challenge_stats,  # <- added here
        "challenge_attempts": challenge_attempts,
        "achievements": achievements,
        "elo_events": elo_events,
        "user_elo": user_elo,
        "question_progress": question_progress
    }

    return analytics
