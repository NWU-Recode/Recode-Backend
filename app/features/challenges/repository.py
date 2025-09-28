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
        resp = await client.table("challenges").select("*").eq("id", challenge_id).single().execute()
        data = resp.data or None
        if data is not None:
            # Normalize tier for API responses: treat 'plain'/'common' as 'base'
            try:
                t = (data.get("tier") or "").strip().lower()
                if t in {"plain", "common"}:
                    data["tier"] = "base"
            except Exception:
                pass
            cache.set(key, data)
        return data

    async def get_challenge_questions(self, challenge_id: str) -> List[Dict[str, Any]]:
        key = f"challenge:{challenge_id}:questions"
        cached = cache.get(key)
        if cached is not None:
            return cached
        client = await get_supabase()
        resp = await client.table("questions").select("*").eq("challenge_id", challenge_id).execute()
        data = resp.data or []
        cache.set(key, data)
        return data

    async def get_open_attempt(self, challenge_id: str, student_number: int) -> Optional[Dict[str, Any]]:
        client = await get_supabase()
        resp = await (
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
        resp = await client.table("challenge_attempts").insert({
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
                        await client.table("challenge_attempts").update({"status": "expired"}).eq("id", existing["id"]).execute()
                        existing["status"] = "expired"
                        return existing
            except Exception:
                pass
        if not existing:
            # Create base attempt with started/deadline
            started_at = now.isoformat()
            deadline_at = (now + timedelta(days=7)).isoformat()
            resp = await client.table("challenge_attempts").insert({
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
            upd = await client.table("challenge_attempts").update(patch).eq("id", existing["id"]).execute()
            if upd.data:
                existing = upd.data[0]
        return existing

    async def list_challenges(self) -> List[Dict[str, Any]]:
        key = "challenge:list"
        cached = cache.get(key)
        if cached is not None:
            return cached
        client = await get_supabase()
        resp = await (
            client.table("challenges")
            .select("*")
            .order("week_number")
            .order("created_at")
            .execute()
        )
        data = resp.data or []
        # Normalize returned tiers for API consumers
        try:
            for item in data:
                if not isinstance(item, dict):
                    continue
                t = (item.get("tier") or "").strip().lower()
                if t in {"plain", "common"}:
                    item["tier"] = "base"
        except Exception:
            pass
        cache.set(key, data)
        return data

    async def list_user_attempts(self, student_number: int) -> List[Dict[str, Any]]:
        client = await get_supabase()
        resp = await client.table("challenge_attempts").select("*").eq("user_id", student_number).execute()  # Supabase stores student_number in user_id column (integer)
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
                "attempts_used": int(q.get("attempts_used") or 0),
            })
        return snapshot

    async def record_question_attempts(
        self,
        attempt_id: str,
        increments: Dict[str, int],
        *,
        max_attempts: int | None = None,
    ) -> None:
        if not increments:
            return
        client = await get_supabase()
        resp = await client.table("challenge_attempts").select("id, snapshot_questions").eq("id", attempt_id).single().execute()
        data = getattr(resp, "data", None) or {}
        snapshot = data.get("snapshot_questions") or []
        updated = False
        now_iso = datetime.now(timezone.utc).isoformat()
        for item in snapshot:
            qid = str(item.get("question_id")) if item.get("question_id") is not None else None
            if qid is None or qid not in increments:
                continue
            attempts_used = int(item.get("attempts_used") or 0) + int(increments[qid])
            if max_attempts is not None:
                attempts_used = min(max_attempts, attempts_used)
            item["attempts_used"] = attempts_used
            item["last_attempted_at"] = now_iso
            updated = True
        if updated:
            await client.table("challenge_attempts").update({"snapshot_questions": snapshot}).eq("id", attempt_id).execute()

    async def get_snapshot(self, attempt: Dict[str, Any]) -> List[Dict[str, Any]]:
        snap = attempt.get("snapshot_questions") or []
        return snap

    async def finalize_attempt(
        self,
        attempt_id: str,
        score: int,
        correct_count: int,
        *,
        duration_seconds: Optional[int] = None,
        tests_total: Optional[int] = None,
        tests_passed: Optional[int] = None,
        elo_delta: Optional[int] = None,
        efficiency_bonus: Optional[int] = None,
    ) -> Dict[str, Any]:
        client = await get_supabase()
        payload: Dict[str, Any] = {
            "score": score,
            "correct_count": correct_count,
            "status": "submitted",
            "submitted_at": "now()",
        }
        optional_fields = {
            "duration_seconds": duration_seconds,
            "tests_total": tests_total,
            "tests_passed": tests_passed,
            "elo_delta": elo_delta,
            "efficiency_bonus": efficiency_bonus,
        }
        for key, value in optional_fields.items():
            if value is not None:
                payload[key] = value
        try:
            resp = await (
                client.table("challenge_attempts")
                .update(payload)
                .eq("id", attempt_id)
                .execute()
            )
        except Exception:
            minimal_payload = {
                "score": score,
                "correct_count": correct_count,
                "status": "submitted",
                "submitted_at": "now()",
            }
            resp = await (
                client.table("challenge_attempts")
                .update(minimal_payload)
                .eq("id", attempt_id)
                .execute()
            )
        if not getattr(resp, "data", None):
            raise RuntimeError("Failed to finalize challenge attempt")
        return resp.data[0]
    # --- Milestone helpers (plain challenge progress) ---
    async def count_plain_completed(self, student_number: int) -> int:
        """Return number of submitted plain (weekly) challenges for user."""
        client = await get_supabase()
        # tier stored as enum -> cast to text compare
        resp = await (
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
        resp = await client.table("challenges").select("id").eq("tier", "plain").execute()
        return len(resp.data or [])

    async def publish_for_week(self, week_number: int) -> Dict[str, int]:
        """Publish challenges for the given week.

        New behaviour:
        - Mark published challenges as 'active' in the status column when published.
        - Set `release_date` to publication timestamp and `due_date` to one week after publication.
        - Enforce only one base (plain/common) challenge may be active for a week; special tiers
          (ruby/emerald/diamond) may coexist with a single base challenge.
        """
        client = await get_supabase()
        week_tag = f"w{week_number:02d}"
        updated = 0
        now = datetime.now(timezone.utc)
        release_iso = now.isoformat()
        due_iso = (now + timedelta(days=7)).isoformat()

        # Fetch candidates by explicit week_number first
        try:
            resp = await client.table("challenges").select("id, tier, slug, status, week_number").eq("week_number", week_number).execute()
            rows = resp.data or []
        except Exception:
            rows = []

        # Fallback to slug-based detection if none found
        if not rows:
            resp_all = await client.table("challenges").select("id, tier, slug, status").execute()
            rows_all = resp_all.data or []
            rows = [r for r in rows_all if week_tag in str(r.get("slug", ""))]

        # Partition into base vs special tiers
        base_rows = [r for r in rows if (r.get("tier") or r.get("kind") or "").strip().lower() in {"plain", "common", "base"}]
        special_rows = [r for r in rows if r not in base_rows]

        # Enforce at most one active base per week: pick the earliest created id if multiple
        chosen_base_id = None
        if base_rows:
            # sort by id deterministically and pick first
            try:
                base_rows_sorted = sorted(base_rows, key=lambda r: str(r.get("id")))
                chosen_base_id = str(base_rows_sorted[0].get("id"))
            except Exception:
                chosen_base_id = str(base_rows[0].get("id"))

        # Apply updates: set status='active', release_date, due_date
        targets = []
        if chosen_base_id:
            targets.append(chosen_base_id)
        # include all special tiers
        for r in special_rows:
            cid = r.get("id")
            if cid:
                targets.append(str(cid))

        # If no explicit targets but rows present, fallback to all ids
        if not targets and rows:
            targets = [str(r.get("id")) for r in rows if r.get("id")]

        for cid in targets:
            payload = {
                "status": "active",
                "release_date": release_iso,
                "due_date": due_iso,
                "week_number": week_number,
            }
            # Attempt update; ignore individual failures but count successes
            try:
                update_resp = await client.table("challenges").update(payload).eq("id", cid).execute()
                if update_resp.data:
                    updated += 1
            except Exception:
                # ignore and continue
                continue
        return {"updated": updated}

    async def list_published_for_week(self, week_number: int) -> List[Dict[str, Any]]:
        """Return all challenges with status='published' for the given week.

        Falls back to slug-based detection if week_number field isn't populated for rows.
        """
        client = await get_supabase()
        week_tag = f"w{week_number:02d}"
        try:
            resp = await client.table("challenges").select("*").eq("week_number", week_number).eq("status", "published").execute()
            rows = resp.data or []
        except Exception:
            rows = []
        if not rows:
            # fallback: look for slug containing week tag among published challenges
            try:
                resp_all = await client.table("challenges").select("*").eq("status", "published").execute()
                all_rows = resp_all.data or []
                rows = [r for r in all_rows if week_tag in str(r.get("slug", ""))]
            except Exception:
                rows = []
        # Normalize tier field for API responses
        try:
            for r in rows:
                if not isinstance(r, dict):
                    continue
                t = (r.get("tier") or r.get("kind") or "").strip().lower()
                if t in {"plain", "common"}:
                    r["tier"] = "base"
        except Exception:
            pass
        return rows

    async def fetch_published_bundles_for_week(self, week_number: int) -> List[Dict[str, Any]]:
        """Return list of published challenge bundles for the given week.

        Each bundle contains the challenge row and its questions. For tier 'plain' (base)
        return up to 5 questions (snapshot design). For other tiers return the single
        canonical question(s) (generator produces 1 question for ruby/emerald in current design).
        """
        client = await get_supabase()
        # fetch published challenges for the week
        try:
            resp = await client.table("challenges").select("*").eq("week_number", week_number).eq("status", "published").order("id").execute()
            rows = resp.data or []
        except Exception:
            # fallback: try by slug week tag
            week_tag = f"w{week_number:02d}"
            resp_all = await client.table("challenges").select("*").eq("status", "published").execute()
            rows = [r for r in (resp_all.data or []) if week_tag in str(r.get("slug", ""))]

        bundles: List[Dict[str, Any]] = []
        for ch in rows:
            cid = ch.get("id")
            if not cid:
                continue
            # fetch questions: for plain return up to 5 (snapshot); for others return questions associated
            try:
                q_resp = await client.table("questions").select("*").eq("challenge_id", cid).execute()
                questions = q_resp.data or []
            except Exception:
                questions = []
            tier = ch.get("tier") or ch.get("kind") or "plain"
            if tier == "plain":
                # ensure deterministic ordering and limit to 5
                questions = sorted(questions, key=lambda q: str(q.get("id")))[:5]
            else:
                # for non-plain, prefer the first question if multiple
                questions = questions[:1]
            bundles.append({"challenge": ch, "questions": questions})
        # Normalize tiers in the returned challenge bundles
        try:
            for b in bundles:
                ch = b.get("challenge") or {}
                if isinstance(ch, dict):
                    t = (ch.get("tier") or ch.get("kind") or "").strip().lower()
                    if t in {"plain", "common"}:
                        ch["tier"] = "base"
        except Exception:
            pass
        return bundles

    async def get_active_for_week(self, week_number: int) -> List[Dict[str, Any]]:
        """Return list of active challenge bundles for the given week.

        This mirrors fetch_published_bundles_for_week but selects by status='active'
        and returns the challenge + its questions + test rows (tests fetched later by submissions service).
        """
        client = await get_supabase()
        try:
            resp = await client.table("challenges").select("*").eq("week_number", week_number).eq("status", "active").order("id").execute()
            rows = resp.data or []
        except Exception:
            rows = []

        bundles: List[Dict[str, Any]] = []

        # Choose up to two challenges: prefer one base (weekly) and one special if present
        base_rows = [r for r in rows if (r.get("tier") or r.get("kind") or "").strip().lower() in {"plain", "common", "base"}]
        special_rows = [r for r in rows if r not in base_rows]

        selected: List[Dict[str, Any]] = []
        if base_rows:
            try:
                base_sorted = sorted(base_rows, key=lambda r: str(r.get("id")))
                selected.append(base_sorted[0])
            except Exception:
                selected.append(base_rows[0])
        if special_rows:
            # pick the first special (deterministic ordering by id)
            try:
                special_sorted = sorted(special_rows, key=lambda r: str(r.get("id")))
                selected.append(special_sorted[0])
            except Exception:
                selected.append(special_rows[0])

        # If none selected (no base/special partition), select up to 2 from rows
        if not selected:
            selected = rows[:2]

        # Enforce max 2
        selected = selected[:2]

        for ch in selected:
            cid = ch.get("id")
            if not cid:
                continue
            try:
                q_resp = await client.table("questions").select("*").eq("challenge_id", cid).order("id").execute()
                questions = q_resp.data or []
            except Exception:
                questions = []

            # For base challenges return up to 5 snapshot questions
            tier = (ch.get("tier") or ch.get("kind") or "").strip().lower()
            if tier in {"plain", "common", "base"}:
                questions = sorted(questions, key=lambda q: str(q.get("id")))[:5]
            else:
                questions = questions[:1]

            # For each question, fetch tests from question_tests (fallback to tests)
            for q in questions:
                qid = q.get("id")
                q_tests = []
                if qid is not None:
                    try:
                        t_resp = await client.table("question_tests").select("*").eq("question_id", qid).order("id").execute()
                        q_tests = t_resp.data or []
                    except Exception:
                        try:
                            t_resp2 = await client.table("tests").select("*").eq("question_id", qid).order("id").execute()
                            q_tests = t_resp2.data or []
                        except Exception:
                            q_tests = []
                q["tests"] = q_tests

            # Normalize tier for API consumers
            try:
                if isinstance(ch, dict):
                    t = (ch.get("tier") or ch.get("kind") or "").strip().lower()
                    if t in {"plain", "common"}:
                        ch["tier"] = "base"
            except Exception:
                pass

            bundles.append({"challenge": ch, "questions": questions})

        return bundles

challenge_repository = ChallengeRepository()


