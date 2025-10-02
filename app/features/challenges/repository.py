from __future__ import annotations
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
import re
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
        try:
            resp = await client.table("challenge_attempts").select("*").eq("user_id", student_number).execute()  # Supabase stores student_number in user_id column (integer)
        except Exception:
            # In demo environments the challenge_attempts table may not exist yet; treat as no attempts.
            return []
        return resp.data or []

    async def list_available_statuses(
        self,
        module_code: str,
        *,
        week_number: Optional[int] = None,
    ) -> List[str]:
        client = await get_supabase()
        try:
            query = (
                client.table("challenges")
                .select("status")
                .eq("module_code", module_code)
            )
            if week_number is not None and week_number > 0:
                query = query.eq("week_number", week_number)
            resp = await query.execute()
        except Exception:
            return []
        seen: set[str] = set()
        statuses: List[str] = []
        for row in resp.data or []:
            value = row.get("status")
            if not value:
                continue
            text = str(value).strip()
            if not text:
                continue
            key = text.lower()
            if key not in seen:
                seen.add(key)
                statuses.append(text)
        return statuses


    def _extract_role(self, current_user: Any) -> str:
        if current_user is None:
            return ""
        if isinstance(current_user, dict):
            role = current_user.get("role")
        else:
            role = getattr(current_user, "role", None)
        return str(role or "").lower()

    def _extract_user_id(self, current_user: Any) -> Optional[int]:
        if current_user is None:
            return None
        value = None
        if isinstance(current_user, dict):
            value = current_user.get("id")
        else:
            value = getattr(current_user, "id", None)
        try:
            return int(value) if value is not None else None
        except Exception:
            return None

    async def resolve_module_access(self, module_code: str, current_user: Any) -> Dict[str, Any]:
        if not module_code:
            raise ValueError("module_code_required")
        client = await get_supabase()
        resp = await (
            client.table("modules")
            .select("id, code, semester_id, lecturer_id")
            .eq("code", module_code)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            raise ValueError("module_not_found")
        module = rows[0]
        role = self._extract_role(current_user)
        user_id = self._extract_user_id(current_user)
        if role == "lecturer":
            ta = await (
                client.table("teaching_assignments")
                .select("id")
                .eq("module_id", module.get("id"))
                .eq("lecturer_profile_id", user_id)
                .limit(1)
                .execute()
            )
            if not (ta.data or []):
                raise PermissionError("module_forbidden")
        elif role == "student":
            enrol = await (
                client.table("enrolments")
                .select("id")
                .eq("module_id", module.get("id"))
                .eq("student_id", user_id)
                .limit(1)
                .execute()
            )
            if not (enrol.data or []):
                raise PermissionError("module_forbidden")
        # admins or other roles fall through
        return module

    async def list_challenges_by_module_and_week(
        self,
        *,
        module_code: str,
        week_number: int,
        statuses: Optional[List[str]] = None,
        include_questions: bool = False,
        limit: int = 20,
    ) -> tuple[List[Dict[str, Any]], Optional[str]]:
        if limit <= 0:
            return [], None

        client = await get_supabase()
        fetch_limit = max(limit, 50)
        statuses_clean = [s.strip().lower() for s in (statuses or []) if s.strip()]

        base_query = client.table("challenges").select("*").eq("module_code", module_code)
        if statuses_clean:
            base_query = base_query.in_("status", statuses_clean)

        try:
            resp = await (
                base_query
                .eq("week_number", week_number)
                .order("release_date", desc=True)
                .order("created_at", desc=True)
                .limit(fetch_limit)
                .execute()
            )
            rows = resp.data or []
        except Exception:
            rows = []

        week_tag = f"w{week_number:02d}"
        if not rows:
            try:
                fallback_resp = await (
                    base_query
                    .order("created_at", desc=True)
                    .limit(fetch_limit)
                    .execute()
                )
                candidates = fallback_resp.data or []
                rows = [row for row in candidates if week_tag in str(row.get("slug", ""))]
            except Exception:
                rows = []

        if not rows:
            return [], None

        rows = rows[:limit]
        challenge_ids = [str(item.get("id")) for item in rows if item.get("id")]

        question_map: Dict[str, List[Dict[str, Any]]] = {}
        question_counts: Dict[str, int] = {cid: 0 for cid in challenge_ids}
        if challenge_ids:
            if include_questions:
                q_query = (
                    client.table("questions")
                    .select("id, challenge_id, question_number, sub_number, question_text, starter_code, reference_solution, language_id, tier")
                    .in_("challenge_id", challenge_ids)
                    .order("question_number")
                    .order("sub_number")
                    .order("id")
                )
            else:
                q_query = (
                    client.table("questions")
                    .select("id, challenge_id")
                    .in_("challenge_id", challenge_ids)
                )
            q_resp = await q_query.execute()
            for item in q_resp.data or []:
                cid = str(item.get("challenge_id"))
                question_counts[cid] = question_counts.get(cid, 0) + 1
                if include_questions:
                    question_map.setdefault(cid, []).append(item)

        items: List[Dict[str, Any]] = []
        for row in rows:
            cid = str(row.get("id"))
            questions = question_map.get(cid, []) if include_questions else None
            items.append({
                "challenge": row,
                "questions": questions,
                "question_count": question_counts.get(cid, 0),
            })

        return items, None

    async def fetch_challenge_with_questions(
        self,
        challenge_id: str,
        *,
        include_questions: bool = False,
        include_testcases: bool = False,
    ) -> Dict[str, Any]:
        client = await get_supabase()
        resp = await client.table("challenges").select("*").eq("id", challenge_id).single().execute()
        data = resp.data or None
        if not data:
            raise ValueError("challenge_not_found")
        questions: List[Dict[str, Any]] = []
        if include_questions:
            q_resp = await (
                client.table("questions")
                .select("*")
                .eq("challenge_id", challenge_id)
                .order("question_number")
                .order("sub_number")
                .order("id")
                .execute()
            )
            questions = q_resp.data or []
            if include_testcases and questions:
                ids = [str(q.get("id")) for q in questions if q.get("id")]
                if ids:
                    tests = await self._fetch_testcases_for_questions(ids)
                    for q in questions:
                        qid = str(q.get("id"))
                        q["testcases"] = tests.get(qid, [])
        return {"challenge": data, "questions": questions}

    async def list_questions_for_challenge(
        self,
        challenge_id: str,
        *,
        include_testcases: bool = False,
    ) -> List[Dict[str, Any]]:
        client = await get_supabase()
        q_resp = await (
            client.table("questions")
            .select("*")
            .eq("challenge_id", challenge_id)
            .order("question_number")
            .order("sub_number")
            .order("id")
            .execute()
        )
        questions = q_resp.data or []
        if not questions:
            return []
        if include_testcases:
            ids = [str(q.get("id")) for q in questions if q.get("id")]
            if ids:
                tests = await self._fetch_testcases_for_questions(ids)
                for q in questions:
                    qid = str(q.get("id"))
                    q["testcases"] = tests.get(qid, [])
        return questions

    async def fetch_question_detail(
        self,
        question_id: str,
        *,
        include_testcases: bool = False,
    ) -> Optional[Dict[str, Any]]:
        client = await get_supabase()
        resp = await client.table("questions").select("*").eq("id", question_id).single().execute()
        question = resp.data or None
        if not question:
            return None
        if include_testcases:
            tests = await self._fetch_testcases_for_questions([question_id])
            question["testcases"] = tests.get(str(question_id), [])
        return question

    async def list_question_testcases(self, question_id: str) -> List[Dict[str, Any]]:
        mapping = await self._fetch_testcases_for_questions([question_id])
        return mapping.get(question_id, [])

    async def _fetch_testcases_for_questions(self, question_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        if not question_ids:
            return {}
        client = await get_supabase()
        tests_map: Dict[str, List[Dict[str, Any]]] = {qid: [] for qid in question_ids}
        try:
            # Try to select the newer column name `expected_output` first; some DBs
            # may still use `expected` so we normalize afterward.
            resp = await (
                client.table("question_tests")
                .select("id, question_id, input, expected_output, visibility, order_index")
                .in_("question_id", question_ids)
                .order("order_index")
                .order("id")
                .execute()
            )
            for item in resp.data or []:
                # Normalize field names for callers
                if item.get("expected_output") is None and item.get("expected") is not None:
                    item["expected_output"] = item.get("expected")
                # Normalize visibility values
                vis = item.get("visibility")
                if isinstance(vis, str) and vis.strip().lower() == "private":
                    item["visibility"] = "hidden"
                qid = str(item.get("question_id"))
                tests_map.setdefault(qid, []).append(item)
        except Exception:
            # If selecting `expected_output` failed because the column doesn't exist,
            # try a looser select that requests `expected` instead.
            try:
                resp = await (
                    client.table("question_tests")
                    .select("id, question_id, input, expected, visibility, order_index")
                    .in_("question_id", question_ids)
                    .order("order_index")
                    .order("id")
                    .execute()
                )
                for item in resp.data or []:
                    # Normalize to expected_output for callers
                    if item.get("expected") is not None and item.get("expected_output") is None:
                        item["expected_output"] = item.get("expected")
                    vis = item.get("visibility")
                    if isinstance(vis, str) and vis.strip().lower() == "private":
                        item["visibility"] = "hidden"
                    qid = str(item.get("question_id"))
                    tests_map.setdefault(qid, []).append(item)
            except Exception:
                pass
        missing = [qid for qid, vals in tests_map.items() if not vals]
        if missing:
            try:
                legacy = await (
                    client.table("tests")
                    .select("id, question_id, input, expected, visibility, order_index")
                    .in_("question_id", missing)
                    .order("order_index")
                    .order("id")
                    .execute()
                )
                for item in legacy.data or []:
                    qid = str(item.get("question_id"))
                    if item.get("expected") and not item.get("expected_output"):
                        item["expected_output"] = item.get("expected")
                    tests_map.setdefault(qid, []).append(item)
            except Exception:
                pass
        return tests_map

    async def _build_snapshot(self, challenge_id: str) -> List[Dict[str, Any]]:
        """Fetch questions and return a frozen snapshot list.

        MVP policy: require at least 5 questions, snapshot the first 5
        ordered by id to align with weekly Common challenge design.
        """
        questions = await self.get_challenge_questions(challenge_id)
        challenge = await self.get_challenge(challenge_id)
        tier_value = str((challenge or {}).get('tier') or 'base').lower()
        challenge_type = str((challenge or {}).get('challenge_type') or 'weekly').lower()
        required = 1 if challenge_type != 'weekly' or tier_value in {'ruby', 'emerald', 'diamond'} else 5
        if len(questions) < required:
            raise ValueError('challenge_not_configured: needs at least %s questions' % required)
        selected = sorted(questions, key=lambda r: str(r.get('id')))[:required]
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

    async def publish_for_week(self, week_number: int, *, module_code: Optional[str] = None, semester_id: Optional[str] = None) -> Dict[str, int]:
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

        # Fetch candidates by explicit week_number first, optionally scoped to a module and semester
        try:
            query = client.table("challenges").select("id, tier, slug, status, week_number, module_code, semester_id")
            query = query.eq("week_number", week_number)
            if module_code:
                query = query.eq("module_code", module_code)
            if semester_id:
                query = query.eq("semester_id", semester_id)
            resp = await query.execute()
            rows = resp.data or []
        except Exception:
            rows = []

        # Fallback to slug-based detection if none found
        if not rows:
            try:
                resp_all = await client.table("challenges").select("id, tier, slug, status, module_code, semester_id").execute()
                rows_all = resp_all.data or []
                if module_code:
                    rows_all = [r for r in rows_all if (r.get("module_code") or None) == module_code]
                if semester_id:
                    rows_all = [r for r in rows_all if (r.get("semester_id") or None) == semester_id]
                rows = [r for r in rows_all if week_tag in str(r.get("slug", ""))]
            except Exception:
                rows = []

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

    async def enforce_active_limit(self, *, module_code: Optional[str] = None, semester_id: Optional[str] = None, keep_count: int = 2) -> Dict[str, int]:
        """Ensure no more than `keep_count` active challenges exist per module+semester scope.

        If module_code and/or semester_id are provided, limit enforcement to that scope; otherwise enforce globally by module.
        Older active challenges (by release_date or created_at) will be set to status 'inactive'.
        """
        client = await get_supabase()
        updated = 0
        try:
            # Fetch active challenges, optionally scoped
            query = client.table("challenges").select("id, module_code, semester_id, release_date, created_at").eq("status", "active")
            if module_code:
                query = query.eq("module_code", module_code)
            if semester_id:
                query = query.eq("semester_id", semester_id)
            resp = await query.execute()
            rows = resp.data or []
        except Exception:
            rows = []

        # Group by module_code + semester_id
        groups: Dict[tuple, List[Dict[str, Any]]] = {}
        for r in rows:
            key = (r.get("module_code") or "", r.get("semester_id") or "")
            groups.setdefault(key, []).append(r)

        for key, items in groups.items():
            if len(items) <= keep_count:
                continue
            # sort by release_date (newest first), fallback to created_at
            def _sort_key(it: Dict[str, Any]):
                return str(it.get("release_date") or it.get("created_at") or "")

            items_sorted = sorted(items, key=_sort_key, reverse=True)
            to_keep = items_sorted[:keep_count]
            to_deactivate = items_sorted[keep_count:]
            for r in to_deactivate:
                cid = r.get("id")
                if not cid:
                    continue
                try:
                    upd = await client.table("challenges").update({"status": "draft"}).eq("id", cid).execute()
                    if getattr(upd, "data", None):
                        updated += 1
                except Exception:
                    continue
        return {"deactivated": updated}

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
        """Return challenge bundles with status in (active, published) for the given week."""
        client = await get_supabase()
        try:
            resp = (
                await client.table("challenges")
                .select("*")
                .in_("status", ["active"])
                .order("id")
                .execute()
            )
            rows = resp.data or []
        except Exception:
            rows = []

        bundles: List[Dict[str, Any]] = []
        if not rows:
            return bundles

        import re as _re

        week_pattern = _re.compile(r"w(\d{2})", _re.IGNORECASE)

        filtered_rows: List[Dict[str, Any]] = []
        for ch in rows:
            week_value = ch.get("week_number")
            effective_week: Optional[int] = None
            if isinstance(week_value, (int, float)):
                effective_week = int(week_value)
            else:
                slug = str(ch.get("slug") or "")
                match_week = week_pattern.search(slug)
                if match_week:
                    try:
                        effective_week = int(match_week.group(1))
                    except Exception:
                        effective_week = None
            if effective_week == week_number:
                filtered_rows.append(ch)

        if not filtered_rows:
            return bundles

        for ch in filtered_rows:
            cid = ch.get("id")
            if not cid:
                continue
            try:
                q_resp = await client.table("questions").select("*").eq("challenge_id", cid).order("id").execute()
                questions = q_resp.data or []
            except Exception:
                questions = []

            tier_value = (ch.get("tier") or ch.get("kind") or "").strip().lower()
            if tier_value in {"plain", "common", "base", "weekly", ""}:
                questions = sorted(questions, key=lambda q: str(q.get("id")))[:5]
            else:
                questions = questions[:1]

            for q in questions:
                qid = q.get("id")
                q_tests: List[Dict[str, Any]] = []
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

            try:
                if isinstance(ch, dict) and tier_value in {"plain", "common", "weekly", ""}:
                    ch["tier"] = "base"
            except Exception:
                pass

            bundles.append({"challenge": ch, "questions": questions})

        return bundles


challenge_repository = ChallengeRepository()

