from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.DB.supabase import get_supabase
from app.common import cache
from app.features.challenges.tier_utils import BASE_TIER, normalise_challenge_tier

try:  # pragma: no cover - optional dependency guard
    from postgrest.exceptions import APIError  # type: ignore
except Exception:  # pragma: no cover - supabase client not available
    APIError = Exception  # type: ignore

logger = logging.getLogger("challenges.repository")

_LOCAL_ATTEMPTS: Dict[str, Dict[str, Any]] = {}
_LOCAL_ATTEMPT_IDS: Dict[str, str] = {}
_LOCAL_FALLBACK_NOTICE_EMITTED = False


def _normalise_student_id(value: Any) -> str:
    try:
        return str(int(value))
    except Exception:
        return str(value)


def _attempt_key(challenge_id: str, student_number: Any) -> str:
    return f"{challenge_id}:{_normalise_student_id(student_number)}"


def _store_local_attempt(attempt: Dict[str, Any]) -> Dict[str, Any]:
    challenge_id = str(attempt.get("challenge_id"))
    student_number = _normalise_student_id(attempt.get("user_id"))
    key = _attempt_key(challenge_id, student_number)
    _LOCAL_ATTEMPTS[key] = attempt
    if attempt.get("id") is not None:
        _LOCAL_ATTEMPT_IDS[str(attempt["id"])] = key
    return attempt


def _get_local_attempt(challenge_id: str, student_number: Any) -> Optional[Dict[str, Any]]:
    return _LOCAL_ATTEMPTS.get(_attempt_key(challenge_id, student_number))


def _get_local_attempt_by_id(attempt_id: str) -> Optional[Dict[str, Any]]:
    key = _LOCAL_ATTEMPT_IDS.get(str(attempt_id))
    if key is None:
        return None
    return _LOCAL_ATTEMPTS.get(key)


def _emit_local_notice() -> None:
    global _LOCAL_FALLBACK_NOTICE_EMITTED
    if not _LOCAL_FALLBACK_NOTICE_EMITTED:
        logger.warning(
            "challenge_attempts table unavailable; using in-memory attempts fallback. Progress will not persist across restarts."
        )
        _LOCAL_FALLBACK_NOTICE_EMITTED = True



class ChallengeRepository:
    """Repository helpers for challenges.

    Note: Supabase stores student numbers in the user_id column for challenge attempts."""
    def _is_attempts_table_missing(self, exc: Exception) -> bool:
        message = getattr(exc, "message", None) or (exc.args[0] if getattr(exc, "args", None) else None)
        if not message:
            message = str(exc)
        text = str(message).lower()
        if "challenge_attempts" not in text:
            return False
        return any(token in text for token in ("schema cache", "does not exist", "not found", "relation"))

    def _normalise_error_message(self, exc: Exception) -> str:
        parts: List[str] = []
        for attr in ("message", "detail", "details", "hint", "code"):
            value = getattr(exc, attr, None)
            if value:
                parts.append(str(value))
        if isinstance(exc, APIError):
            response = getattr(exc, "response", None)
            try:
                if response is not None:
                    payload = response.json()
                    if isinstance(payload, dict):
                        parts.extend(str(item) for item in payload.values() if item)
            except Exception:
                pass
        if getattr(exc, "args", None):
            parts.extend(str(arg) for arg in exc.args if arg)
        text = " ".join(parts).strip()
        if not text:
            text = str(exc)
        return text.lower()

    def _is_unique_attempt_violation(self, exc: Exception) -> bool:
        text = self._normalise_error_message(exc)
        if not text:
            return False
        conflict_tokens = (
            "uq_challenge_attempts_challenge_user",
            "duplicate key",
            "unique constraint",
            "23505",
        )
        return any(token in text for token in conflict_tokens)

    async def _fetch_existing_attempt(
        self,
        challenge_id: str,
        student_number: int,
        *,
        client: Any | None = None,
    ) -> Optional[Dict[str, Any]]:
        local_attempt = _get_local_attempt(challenge_id, student_number)
        if local_attempt:
            return local_attempt

        try:
            if client is None:
                client = await get_supabase()
            resp = await (
                client.table("challenge_attempts")
                .select("*")
                .eq("challenge_id", challenge_id)
                .eq("user_id", student_number)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            if self._is_attempts_table_missing(exc):
                return local_attempt
            raise

        data = getattr(resp, "data", None) or []
        if data:
            return data[0]
        return None

    async def _ensure_local_attempt_defaults(
        self,
        attempt: Dict[str, Any],
        challenge_id: str,
        student_number: int,
        *,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        attempt["challenge_id"] = challenge_id
        attempt["user_id"] = attempt.get("user_id") if attempt.get("user_id") is not None else student_number
        status = str(attempt.get("status") or "").lower()
        if status not in {"open", "submitted", "expired"}:
            attempt["status"] = "open"
        deadline = attempt.get("deadline_at")
        if not attempt.get("started_at"):
            attempt["started_at"] = now.isoformat()
        if not deadline:
            attempt["deadline_at"] = (now + timedelta(days=7)).isoformat()
        deadline = attempt.get("deadline_at")
        if deadline:
            try:
                deadline_dt = datetime.fromisoformat(str(deadline).replace("Z", "+00:00"))
            except Exception:
                deadline_dt = None
            if deadline_dt and now > deadline_dt:
                attempt["status"] = "expired"
        if not attempt.get("snapshot_questions"):
            attempt["snapshot_questions"] = await self._build_snapshot(challenge_id)
        attempt.setdefault("created_at", attempt.get("started_at", now.isoformat()))
        attempt["updated_at"] = now.isoformat()
        attempt["_local"] = True
        _emit_local_notice()
        return _store_local_attempt(attempt)

    async def _create_local_attempt(
        self, challenge_id: str, student_number: int, *, started_at: Optional[str] = None, deadline_at: Optional[str] = None
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        attempt = {
            "id": f"local-{uuid4()}",
            "challenge_id": challenge_id,
            "user_id": student_number,
            "status": "open",
            "started_at": started_at or now.isoformat(),
            "deadline_at": deadline_at or (now + timedelta(days=7)).isoformat(),
            "snapshot_questions": [],
        }
        return await self._ensure_local_attempt_defaults(attempt, challenge_id, student_number, now=now)

    def _update_local_attempt_attempts(
        self, attempt: Dict[str, Any], increments: Dict[str, int], *, max_attempts: int | None = None
    ) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        snapshot = attempt.get("snapshot_questions") or []
        for item in snapshot:
            qid = str(item.get("question_id")) if item.get("question_id") is not None else None
            if qid is None or qid not in increments:
                continue
            attempts_used = int(item.get("attempts_used") or 0) + int(increments[qid])
            if max_attempts is not None:
                attempts_used = min(max_attempts, attempts_used)
            item["attempts_used"] = attempts_used
            item["last_attempted_at"] = now_iso
        attempt["snapshot_questions"] = snapshot
        attempt["updated_at"] = now_iso
        _store_local_attempt(attempt)

    async def get_challenge(self, challenge_id: str) -> Optional[Dict[str, Any]]:
        key = f"challenge:id:{challenge_id}"
        cached = cache.get(key)
        if cached is not None:
            return cached
        client = await get_supabase()
        resp = await client.table("challenges").select("*").eq("id", challenge_id).single().execute()
        data = resp.data or None
        if data is not None:
            try:
                tier_value = normalise_challenge_tier(data.get("tier"))
                if tier_value:
                    data["tier"] = tier_value
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
        try:
            client = await get_supabase()
        except Exception as exc:
            if self._is_attempts_table_missing(exc):
                attempt = _get_local_attempt(challenge_id, student_number)
                if attempt:
                    return attempt
                _emit_local_notice()
                return None
            raise
        try:
            resp = await (
                client.table("challenge_attempts")
                .select("*")
                .eq("challenge_id", challenge_id)
                .eq("user_id", student_number)  # Supabase stores student_number in user_id column (integer)
                .eq("status", "open")
                .limit(1)
                .execute()
            )
        except Exception as exc:
            if self._is_attempts_table_missing(exc):
                attempt = _get_local_attempt(challenge_id, student_number)
                if attempt:
                    return attempt
                _emit_local_notice()
                return None
            raise
        if resp.data:
            return resp.data[0]
        fallback = _get_local_attempt(challenge_id, student_number)
        if fallback:
            return fallback
        return None

    async def start_attempt(self, challenge_id: str, student_number: int) -> Dict[str, Any]:
        try:
            client = await get_supabase()
        except Exception as exc:
            if self._is_attempts_table_missing(exc):
                return await self._create_local_attempt(challenge_id, student_number)
            raise
        try:
            resp = await client.table("challenge_attempts").insert({
                "challenge_id": challenge_id,
                "user_id": student_number,  # Supabase stores student_number in user_id column (integer)
                "status": "open",
            }).execute()
        except Exception as exc:
            if self._is_attempts_table_missing(exc):
                return await self._create_local_attempt(challenge_id, student_number)
            if self._is_unique_attempt_violation(exc):
                existing = await self._fetch_existing_attempt(challenge_id, student_number, client=client)
                if existing:
                    return existing
            raise
        if not resp.data:
            raise RuntimeError("Failed to start challenge attempt")
        return resp.data[0]

    async def create_or_get_open_attempt(self, challenge_id: str, student_number: int) -> Dict[str, Any]:
        """Return an open attempt creating + snapshotting + deadlines if needed.

        Deadline is 7 days from first start. Expire if exceeded.
        """
        existing = await self.get_open_attempt(challenge_id, student_number)
        now = datetime.now(timezone.utc)

        if existing and existing.get("_local"):
            return await self._ensure_local_attempt_defaults(existing, challenge_id, student_number, now=now)

        client = None

        if existing:
            deadline_at = existing.get("deadline_at")
            try:
                if deadline_at:
                    deadline_dt = datetime.fromisoformat(str(deadline_at).replace("Z", "+00:00"))
                else:
                    deadline_dt = None
            except Exception:
                deadline_dt = None
            if deadline_dt and now > deadline_dt:
                try:
                    if client is None:
                        client = await get_supabase()
                    await client.table("challenge_attempts").update({"status": "expired"}).eq("id", existing["id"]).execute()
                except Exception as exc:
                    if self._is_attempts_table_missing(exc):
                        existing["status"] = "expired"
                        return await self._ensure_local_attempt_defaults(existing, challenge_id, student_number, now=now)
                    raise
                existing["status"] = "expired"
                return existing

        reopened_existing = False

        if not existing:
            started_at = now.isoformat()
            deadline_at = (now + timedelta(days=7)).isoformat()
            try:
                if client is None:
                    client = await get_supabase()
                resp = await client.table("challenge_attempts").insert({
                    "challenge_id": challenge_id,
                    "user_id": student_number,  # Supabase stores student_number in user_id column (integer)
                    "status": "open",
                    "started_at": started_at,
                    "deadline_at": deadline_at,
                }).execute()
            except Exception as exc:
                if self._is_attempts_table_missing(exc):
                    return await self._create_local_attempt(
                        challenge_id, student_number, started_at=started_at, deadline_at=deadline_at
                    )
                if self._is_unique_attempt_violation(exc):
                    existing = await self._fetch_existing_attempt(
                        challenge_id,
                        student_number,
                        client=client,
                    )
                    if existing is None:
                        raise
                    reopened_existing = True
                else:
                    raise
            else:
                if not resp.data:
                    raise RuntimeError("Failed to start challenge attempt")
                existing = resp.data[0]

        if existing is None:
            raise RuntimeError("Failed to create or fetch challenge attempt")

        if client is None:
            client = await get_supabase()

        patch: Dict[str, Any] = {}
        if reopened_existing:
            patch["started_at"] = now.isoformat()
            patch["deadline_at"] = (now + timedelta(days=7)).isoformat()
            patch["submitted_at"] = None
            patch["snapshot_questions"] = await self._build_snapshot(challenge_id)
        else:
            if not existing.get("snapshot_questions"):
                patch["snapshot_questions"] = await self._build_snapshot(challenge_id)
            if not existing.get("started_at"):
                patch["started_at"] = now.isoformat()
            if not existing.get("deadline_at"):
                patch["deadline_at"] = (now + timedelta(days=7)).isoformat()
        if reopened_existing and existing.get("status") != "open":
            patch["status"] = "open"
        if patch:
            try:
                upd = await client.table("challenge_attempts").update(patch).eq("id", existing["id"]).execute()
            except Exception as exc:
                if self._is_attempts_table_missing(exc):
                    existing.update(patch)
                    return await self._ensure_local_attempt_defaults(existing, challenge_id, student_number, now=now)
                raise
            if upd.data:
                existing = upd.data[0]
            else:
                existing.update(patch)
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
                if normalise_challenge_tier(t) == BASE_TIER:
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
        ordered by id to align with weekly base challenge design.
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

        local_attempt = _get_local_attempt_by_id(attempt_id)
        if local_attempt:
            self._update_local_attempt_attempts(local_attempt, increments, max_attempts=max_attempts)
            return

        try:
            client = await get_supabase()
        except Exception as exc:
            if self._is_attempts_table_missing(exc):
                return
            raise

        try:
            resp = await (
                client.table("challenge_attempts")
                .select("id, snapshot_questions")
                .eq("id", attempt_id)
                .single()
                .execute()
            )
        except Exception as exc:
            if self._is_attempts_table_missing(exc):
                return
            raise

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
            try:
                await client.table("challenge_attempts").update({"snapshot_questions": snapshot}).eq("id", attempt_id).execute()
            except Exception as exc:
                if self._is_attempts_table_missing(exc):
                    return
                raise


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
        local_attempt = _get_local_attempt_by_id(attempt_id)
        if local_attempt:
            now_iso = datetime.now(timezone.utc).isoformat()
            local_attempt.update({
                "score": score,
                "correct_count": correct_count,
                "status": "submitted",
                "submitted_at": now_iso,
            })
            if duration_seconds is not None:
                local_attempt["duration_seconds"] = duration_seconds
            if tests_total is not None:
                local_attempt["tests_total"] = tests_total
            if tests_passed is not None:
                local_attempt["tests_passed"] = tests_passed
            if elo_delta is not None:
                local_attempt["elo_delta"] = elo_delta
            if efficiency_bonus is not None:
                local_attempt["efficiency_bonus"] = efficiency_bonus
            _store_local_attempt(local_attempt)
            return local_attempt

        try:
            client = await get_supabase()
        except Exception as exc:
            if self._is_attempts_table_missing(exc):
                raise RuntimeError("challenge_attempts_unavailable") from exc
            raise

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
        except Exception as exc:
            if self._is_attempts_table_missing(exc):
                raise RuntimeError("challenge_attempts_unavailable") from exc
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

    # --- Milestone helpers (base challenge progress) ---
    async def count_base_completed(self, student_number: int) -> int:
        """Return number of submitted base (weekly) challenges for user."""
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
            challenge_meta = row.get("challenge")
            tier = None
            if isinstance(challenge_meta, dict):
                tier = challenge_meta.get("tier")
            elif isinstance(challenge_meta, list) and challenge_meta:
                tier = challenge_meta[0].get("tier")
            if normalise_challenge_tier(tier) == BASE_TIER:
                count += 1
        return count

    async def total_base_planned(self) -> int:
        """Total number of planned base challenges (configured)."""
        client = await get_supabase()
        resp = await client.table("challenges").select("id, tier").execute()
        rows = resp.data or []
        return sum(1 for row in rows if normalise_challenge_tier(row.get("tier")) == BASE_TIER)

    async def publish_for_week(self, week_number: int, *, module_code: Optional[str] = None, semester_id: Optional[str] = None) -> Dict[str, int]:
        """Publish challenges for the given week.

        New behaviour:
        - Mark published challenges as 'active' in the status column when published.
        - Set `release_date` to publication timestamp and `due_date` to one week after publication.
        - Enforce only one base challenge may be active for a week; special tiers
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
        base_rows = [r for r in rows if normalise_challenge_tier(r.get("tier") or r.get("kind")) == BASE_TIER]
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
                if normalise_challenge_tier(t) == BASE_TIER:
                    r["tier"] = "base"
        except Exception:
            pass
        return rows

    async def fetch_published_bundles_for_week(self, week_number: int) -> List[Dict[str, Any]]:
        """Return list of published challenge bundles for the given week.

        Each bundle contains the challenge row and its questions. For the base tier
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
            # fetch questions: for the base tier return up to 5 (snapshot); for others return questions associated
            try:
                q_resp = await client.table("questions").select("*").eq("challenge_id", cid).execute()
                questions = q_resp.data or []
            except Exception:
                questions = []
            tier = normalise_challenge_tier(ch.get("tier") or ch.get("kind")) or BASE_TIER
            if tier == BASE_TIER:
                # ensure deterministic ordering and limit to 5
                questions = sorted(questions, key=lambda q: str(q.get("id")))[:5]
            else:
                # for non-base tiers, prefer the first question if multiple
                questions = questions[:1]
            bundles.append({"challenge": ch, "questions": questions})
        # Normalize tiers in the returned challenge bundles
        try:
            for b in bundles:
                ch = b.get("challenge") or {}
                if isinstance(ch, dict):
                    tier_value = normalise_challenge_tier(ch.get("tier") or ch.get("kind"))
                    if tier_value:
                        ch["tier"] = tier_value
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

            tier_value = normalise_challenge_tier(ch.get("tier") or ch.get("kind")) or (ch.get("tier") or ch.get("kind") or "").strip().lower()
            if tier_value == BASE_TIER:
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
                if isinstance(ch, dict):
                    canonical_tier = normalise_challenge_tier(ch.get("tier") or ch.get("kind"))
                    if canonical_tier:
                        ch["tier"] = canonical_tier
            except Exception:
                pass

            bundles.append({"challenge": ch, "questions": questions})

        return bundles


challenge_repository = ChallengeRepository()

