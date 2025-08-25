from __future__ import annotations
from typing import Dict, List, Any, Tuple
from app.db.supabase import get_supabase
#from app.features.dashboard.tests.fakesupabase import get_supabase




class DashboardRepository:
    async def count_profiles(self, active_only: bool = False) -> int:
        query = get_supabase().table("profiles").select("id", count="exact")
        if active_only:
            query = query.eq("is_active", True)
        res = query.execute()
        return getattr(res, "count", None) or len(res.data or [])

    async def count_challenges(self) -> int:
        res = get_supabase().table("challenges").select("id", count="exact").execute()
        return getattr(res, "count", None) or len(res.data or [])

    async def count_challenge_attempts(self) -> int:
        res = get_supabase().table("challenge_attempts").select("id", count="exact").execute()
        return getattr(res, "count", None) or len(res.data or [])

    async def leaderboard(self, limit: int = 10) -> List[Dict[str, Any]]:
        attempts_res = get_supabase().table("challenge_attempts").select("user_id,score").execute()
        attempts = attempts_res.data or []

        totals: Dict[str, int] = {}
        for row in attempts:
            uid = row.get("user_id")
            score = row.get("score") or 0
            if not uid:
                continue
            totals[uid] = totals.get(uid, 0) + int(score)

        if not totals:
            return []

        user_ids = list(totals.keys())
        profiles_res = get_supabase().table("profiles").select("id,full_name,email").in_("id", user_ids).execute()
        profiles = {p["id"]: p for p in (profiles_res.data or [])}

        rows: List[Tuple[str, str, str, int]] = []
        for uid, total in totals.items():
            prof = profiles.get(uid, {})
            full_name = prof.get("full_name") or ""
            email = prof.get("email") or ""
            rows.append((uid, full_name, email, total))

        rows.sort(key=lambda x: x[3], reverse=True)
        rows = rows[: max(1, int(limit))]

        return [
            {"user_id": uid, "full_name": full_name or email, "email": email, "score": score}
            for uid, full_name, email, score in rows
        ]
        
# app/features/dashboard/repository.py
dashboard_repository = DashboardRepository()
