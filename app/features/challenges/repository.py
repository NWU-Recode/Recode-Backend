from __future__ import annotations
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
from app.DB.supabase import get_supabase
from app.common import cache

class ChallengeRepository:
    """Repository helpers for challenges.

    Note: Supabase stores student numbers in the user_id column for challenge attempts."""
    async def get_challenge(self, challenge_id: str) -> Optional[Dict[str, Any]]:
        key = f"challenge:id:{challenge_id}"
        cached = cache.get(key)
        if cached is not None:
            return cached
        client = await get_supabase()
        resp = client.table("challenges").select("*").eq("id", challenge_id).single().execute()
        data = resp.data or None
        if data is not None:
            cache.set(key, data)
        return data

    async def get_challenge_questions(self, challenge_id: str) -> List[Dict[str, Any]]:
        key = f"challenge:{challenge_id}:questions"
        cached = cache.get(key)
        if cached is not None:
            return cached
        client = await get_supabase()
        resp = client.table("questions").select("*").eq("challenge_id", challenge_id).execute()
        data = resp.data or []
        cache.set(key, data)
        return data

    async def get_open_attempt(self, challenge_id: str, student_number: int) -> Optional[Dict[str, Any]]:
        client = await get_supabase()
        resp = (
            client.table("challenge_attempts")
            .select("*")
            .eq("challenge_id", challenge_id)
            .eq("user_id", student_number)  # Supabase stores student_number in user_id column (integer)
            .eq("status", "open")
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]
        return None

    async def start_attempt(self, challenge_id: str, student_number: int) -> Dict[str, Any]:
        client = await get_supabase()
        resp = client.table("challenge_attempts").insert({
            "challenge_id": challenge_id,
            "user_id": student_number,  # Supabase stores student_number in user_id column (integer)
            "status": "open",
        }).execute()
        if not resp.data:
            raise RuntimeError("Failed to start challenge attempt")
        return resp.data[0]

    async def create_or_get_open_attempt(self, challenge_id: str, student_number: int) -> Dict[str, Any]:
        """Return an open attempt creating + snapshotting + deadlines if needed.

        Deadline is 7 days from first start. Expire if exceeded.
        """
        existing = await self.get_open_attempt(challenge_id, student_number)
        now = datetime.now(timezone.utc)
        client = await get_supabase()
        if existing:
            started_at = existing.get("started_at")
            deadline_at = existing.get("deadline_at")
            # Expire if deadline passed
            try:
                if deadline_at:
                    ddt = datetime.fromisoformat(str(deadline_at).replace("Z", "+00:00"))
                    if now > ddt:
                        client.table("challenge_attempts").update({"status": "expired"}).eq("id", existing["id"]).execute()
                        existing["status"] = "expired"
                        return existing
            except Exception:
                pass
        if not existing:
            # Create base attempt with started/deadline
            started_at = now.isoformat()
            deadline_at = (now + timedelta(days=7)).isoformat()
            resp = client.table("challenge_attempts").insert({
                "challenge_id": challenge_id,
                "user_id": student_number,  # Supabase stores student_number in user_id column (integer)
                "status": "open",
                "started_at": started_at,
                "deadline_at": deadline_at,
            }).execute()
            if not resp.data:
                raise RuntimeError("Failed to start challenge attempt")
            existing = resp.data[0]
        # Ensure snapshot exists & set started/deadline if missing legacy rows
        patch: Dict[str, Any] = {}
        if not existing.get("snapshot_questions"):
            snapshot = await self._build_snapshot(challenge_id)
            patch["snapshot_questions"] = snapshot
        if not existing.get("started_at"):
            patch["started_at"] = now.isoformat()
        if not existing.get("deadline_at"):
            patch["deadline_at"] = (now + timedelta(days=7)).isoformat()
        if patch:
            upd = client.table("challenge_attempts").update(patch).eq("id", existing["id"]).execute()
            if upd.data:
                existing = upd.data[0]
        return existing

    async def list_challenges(self) -> List[Dict[str, Any]]:
        key = "challenge:list"
        cached = cache.get(key)
        if cached is not None:
            return cached
        client = await get_supabase()
        resp = (
            client.table("challenges")
            .select("*")
            .order("week_number")
            .order("created_at")
            .execute()
        )
        data = resp.data or []
        cache.set(key, data)
        return data

    async def list_user_attempts(self, student_number: int) -> List[Dict[str, Any]]:
        client = await get_supabase()
        resp = client.table("challenge_attempts").select("*").eq("user_id", student_number).execute()  # Supabase stores student_number in user_id column (integer)
        return resp.data or []

    async def _build_snapshot(self, challenge_id: str) -> List[Dict[str, Any]]:
        """Fetch questions and return a frozen snapshot list.

        MVP policy: require at least 5 questions, snapshot the first 5
        ordered by id to align with weekly Common challenge design.
        """
        questions = await self.get_challenge_questions(challenge_id)
        if len(questions) < 5:
            raise ValueError("challenge_not_configured: needs at least 5 questions")
        selected = sorted(questions, key=lambda r: str(r.get("id")))[:5]
        snapshot: List[Dict[str, Any]] = []
        for idx, q in enumerate(selected):
            snapshot.append({
                "question_id": str(q["id"]),
                "expected_output": (q.get("expected_output") or "").strip(),
                "language_id": q.get("language_id"),
                "max_time_ms": q.get("max_time_ms"),
                "max_memory_kb": q.get("max_memory_kb"),
                "points": q.get("points", 1),
                "order_index": idx,
                "version": 1,
            })
        return snapshot

    async def get_snapshot(self, attempt: Dict[str, Any]) -> List[Dict[str, Any]]:
        snap = attempt.get("snapshot_questions") or []
        return snap

    async def finalize_attempt(self, attempt_id: str, score: int, correct_count: int) -> Dict[str, Any]:
        client = await get_supabase()
        resp = (
            client.table("challenge_attempts")
            .update({
                "score": score,
                "correct_count": correct_count,
                "status": "submitted",
                "submitted_at": "now()",
            })
            .eq("id", attempt_id)
            .execute()
        )
        if not resp.data:
            raise RuntimeError("Failed to finalize challenge attempt")
        return resp.data[0]

    # --- Milestone helpers (plain challenge progress) ---
    async def count_plain_completed(self, student_number: int) -> int:
        """Return number of submitted plain (weekly) challenges for user."""
        client = await get_supabase()
        # tier stored as enum -> cast to text compare
        resp = (
            client.table("challenge_attempts")
            .select("id, challenge:challenges(tier)")
            .eq("user_id", student_number)  # Supabase stores student_number in user_id column (integer)
            .eq("status", "submitted")
            .execute()
        )
        data = resp.data or []
        count = 0
        for row in data:
            ch = row.get("challenge")
            # PostgREST join returns object or list
            tier = None
            if isinstance(ch, dict):
                tier = ch.get("tier")
            elif isinstance(ch, list) and ch:
                tier = ch[0].get("tier")
            if tier == "plain":
                count += 1
        return count

    async def total_plain_planned(self) -> int:
        """Total number of planned plain challenges (configured)."""
        client = await get_supabase()
        resp = client.table("challenges").select("id").eq("tier", "plain").execute()
        return len(resp.data or [])

    async def publish_for_week(self, week_number: int) -> Dict[str, int]:
        """Set status='published' for all challenges inferred for a given week."""
        client = await get_supabase()
        week_tag = f"w{week_number:02d}"
        updated = 0
        try:
            resp = client.table("challenges").select("id, slug, status, week_number").eq("week_number", week_number).execute()
            rows = resp.data or []
        except Exception:
            rows = []
        ids = [str(r.get("id")) for r in rows if r.get("id")]
        if not ids:
            resp_all = client.table("challenges").select("id, slug").execute()
            rows_all = resp_all.data or []
            ids = [str(r.get("id")) for r in rows_all if week_tag in str(r.get("slug", ""))]
        for cid in ids:
            update_resp = client.table("challenges").update({"status": "published"}).eq("id", cid).execute()
            if update_resp.data:
                updated += 1
        return {"updated": updated}

challenge_repository = ChallengeRepository()
