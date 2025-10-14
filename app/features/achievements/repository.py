from __future__ import annotations
import logging
from datetime import datetime, timezone, date
from typing import Any, Dict, Iterable, List, Optional

from app.DB.supabase import get_supabase

logger = logging.getLogger("achievements.repository")


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except Exception:  # pragma: no cover - defensive branch
            return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:  # pragma: no cover - defensive branch
            return None
    return None


class AchievementsRepository:
    """Low-level access helpers for achievements related Supabase tables.

    Every method is resilient to partially configured schemas – the production
    database evolved quickly and some columns may be renamed. The repository
    therefore normalises common aliases so that higher level services can focus
    on the business rules instead of fiddling with column names.
    """

    # --- Generic helpers -------------------------------------------------

    async def _execute(self, query, op: str) -> Any:
        """Execute a Supabase query and log failures without exploding."""

        try:
            return await query
        except Exception as exc:  # pragma: no cover - Supabase client failure
            logger.warning("supabase_%s_failed error=%s", op, exc)
            return None

    async def _client(self):
        return await get_supabase()

    # --- Challenge attempts ----------------------------------------------

    async def fetch_challenge_attempt(self, attempt_id: str) -> Optional[Dict[str, Any]]:
        client = await self._client()
        query = client.table("challenge_attempts").select("*").eq("id", attempt_id).single()
        resp = await self._execute(query.execute(), op="challenge_attempts.single")
        data = getattr(resp, "data", None)
        return data or None

    async def fetch_challenge(self, challenge_id: str) -> Optional[Dict[str, Any]]:
        client = await self._client()
        query = client.table("challenges").select("*").eq("id", challenge_id).single()
        resp = await self._execute(query.execute(), op="challenges.single")
        data = getattr(resp, "data", None)
        return data or None

    async def list_submitted_attempts(self, user_id: str) -> List[Dict[str, Any]]:
        client = await self._client()
        query = (
            client.table("challenge_attempts")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "submitted")
        )
        resp = await self._execute(query.execute(), op="challenge_attempts.submitted")
        data = getattr(resp, "data", None)
        return data or []

    async def list_attempts_for_challenge(self, challenge_id: str) -> List[Dict[str, Any]]:
        client = await self._client()
        query = (
            client.table("challenge_attempts")
            .select("*")
            .eq("challenge_id", challenge_id)
            .eq("status", "submitted")
        )
        resp = await self._execute(query.execute(), op="challenge_attempts.by_challenge")
        data = getattr(resp, "data", None)
        return data or []

    # --- Elo --------------------------------------------------------------

    async def get_user_elo(
        self,
        user_id: str,
        module_code: Optional[str] = None,
        semester_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        # Determine if user_id is an integer (profile_id) or UUID
        profile_id = None
        uuid_user_id = None
        try:
            profile_id = int(user_id)
        except (ValueError, TypeError):
            uuid_user_id = user_id
            
        client = await self._client()
        
        # If no module/semester filters, just get the latest record
        if module_code is None and semester_id is None:
            if profile_id is not None:
                query = (
                    client.table("user_elo")
                    .select("*")
                    .eq("student_id", profile_id)
                    .order("updated_at", desc=True)
                    .limit(1)
                )
            else:
                query = (
                    client.table("user_elo")
                    .select("*")
                    .eq("user_id", uuid_user_id)
                    .order("updated_at", desc=True)
                    .limit(1)
                )
            resp = await self._execute(query.execute(), op="user_elo.latest")
            data = getattr(resp, "data", None)
            if isinstance(data, list):
                return data[0] if data else None
            if isinstance(data, dict):
                return data
            return None

        # Query with filters
        if profile_id is not None:
            query = client.table("user_elo").select("*").eq("student_id", profile_id)
        else:
            query = client.table("user_elo").select("*").eq("user_id", uuid_user_id)
            
        if module_code is not None:
            query = query.eq("module_code", module_code)
        if semester_id is not None:
            query = query.eq("semester_id", semester_id)
        resp = await self._execute(query.maybe_single().execute(), op="user_elo.scoped")
        data = getattr(resp, "data", None)
        if isinstance(data, list):
            return data[0] if data else None
        return data or None

    async def insert_user_elo(
        self,
        user_id: str,
        elo_points: int,
        gpa: Optional[float],
        module_code: Optional[str] = None,
        semester_id: Optional[str] = None,
        semester_start: Optional[date] = None,
        semester_end: Optional[date] = None,
    ) -> Optional[Dict[str, Any]]:
        # Determine if user_id is an integer (profile_id) or UUID
        profile_id = None
        uuid_user_id = None
        try:
            profile_id = int(user_id)
        except (ValueError, TypeError):
            uuid_user_id = user_id
        
        payload: Dict[str, Any] = {
            "elo_points": elo_points,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Set both profile_id and user_id for compatibility
        if profile_id is not None:
            payload["profile_id"] = profile_id
            payload["student_id"] = profile_id  # user_elo uses student_id as PK
        if uuid_user_id is not None:
            payload["user_id"] = uuid_user_id
            
        if gpa is not None:
            payload["running_gpa"] = gpa
        optional_fields: Dict[str, Any] = {}
        if module_code is not None:
            optional_fields["module_code"] = module_code
        if semester_id is not None:
            optional_fields["semester_id"] = semester_id
        if semester_start is not None:
            optional_fields["semester_start"] = semester_start.isoformat()
        if semester_end is not None:
            optional_fields["semester_end"] = semester_end.isoformat()
        payload.update(optional_fields)
        client = await self._client()
        resp = await self._execute(client.table("user_elo").insert(payload).execute(), op="user_elo.insert")
        data = getattr(resp, "data", None)
        if not data and optional_fields:
            fallback_payload: Dict[str, Any] = {
                "elo_points": elo_points,
                "updated_at": payload["updated_at"],
            }
            if profile_id is not None:
                fallback_payload["profile_id"] = profile_id
                fallback_payload["student_id"] = profile_id
            if uuid_user_id is not None:
                fallback_payload["user_id"] = uuid_user_id
            if gpa is not None:
                fallback_payload["running_gpa"] = gpa
            resp = await self._execute(
                client.table("user_elo").insert(fallback_payload).execute(),
                op="user_elo.insert_fallback",
            )
            data = getattr(resp, "data", None)
        if isinstance(data, list):
            return data[0] if data else None
        return data or None

    async def update_user_elo(
        self,
        user_id: str,
        elo_points: int,
        gpa: Optional[float],
        module_code: Optional[str] = None,
        semester_id: Optional[str] = None,
        semester_start: Optional[date] = None,
        semester_end: Optional[date] = None,
        elo_delta: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        # Determine if user_id is an integer (profile_id) or UUID
        profile_id = None
        uuid_user_id = None
        try:
            profile_id = int(user_id)
        except (ValueError, TypeError):
            uuid_user_id = user_id
            
        payload: Dict[str, Any] = {
            "elo_points": elo_points,
            "current_elo": elo_points,  # Also update current_elo field
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if gpa is not None:
            payload["running_gpa"] = gpa
        if module_code is not None:
            payload.setdefault("module_code", module_code)
        if semester_id is not None:
            payload.setdefault("semester_id", semester_id)
        if semester_start is not None:
            payload.setdefault("semester_start", semester_start.isoformat())
        if semester_end is not None:
            payload.setdefault("semester_end", semester_end.isoformat())
        
        # If elo_delta is positive, update total_awarded_elo and last_awarded_at
        if elo_delta is not None and elo_delta > 0:
            payload["last_awarded_at"] = datetime.now(timezone.utc).isoformat()
            # We need to increment total_awarded_elo, so first fetch current value
            client = await self._client()
            if profile_id is not None:
                current_query = client.table("user_elo").select("total_awarded_elo").eq("student_id", profile_id)
            else:
                current_query = client.table("user_elo").select("total_awarded_elo").eq("user_id", uuid_user_id)
            
            try:
                current_resp = await self._execute(current_query.execute(), op="user_elo.select_total")
                current_data = getattr(current_resp, "data", None)
                if current_data and len(current_data) > 0:
                    current_total = current_data[0].get("total_awarded_elo") or 0
                    payload["total_awarded_elo"] = current_total + elo_delta
                else:
                    payload["total_awarded_elo"] = elo_delta
            except Exception:
                # If we can't fetch, just set it to the delta
                payload["total_awarded_elo"] = elo_delta
        else:
            client = await self._client()
            
        # Query by the appropriate ID field
        if profile_id is not None:
            query = client.table("user_elo").update(payload).eq("student_id", profile_id)
        else:
            query = client.table("user_elo").update(payload).eq("user_id", uuid_user_id)
            
        if module_code is not None:
            query = query.eq("module_code", module_code)
        if semester_id is not None:
            query = query.eq("semester_id", semester_id)
        resp = await self._execute(query.execute(), op="user_elo.update")
        data = getattr(resp, "data", None)
        if isinstance(data, list) and data:
            return data[0]
        if isinstance(data, dict) and data:
            return data
        return await self.insert_user_elo(
            user_id,
            elo_points=elo_points,
            gpa=gpa,
            module_code=module_code,
            semester_id=semester_id,
            semester_start=semester_start,
            semester_end=semester_end,
        )

    async def log_elo_event(self, payload: Dict[str, Any]) -> None:
        client = await self._client()
        query = client.table("elo_events").insert(payload)
        await self._execute(query.execute(), op="elo_events.insert")

    # --- User Scores & Progress -------------------------------------------

    async def update_user_scores(
        self,
        user_id: str,
        elo: int,
        gpa: float,
        questions_attempted: int = 0,
        questions_passed: int = 0,
        challenges_completed: int = 0,
        badges: int = 0,
    ) -> None:
        """Update or insert user_scores table with overall performance metrics.
        For counters (questions_attempted, etc.), this INCREMENTS the existing values.
        For elo/gpa, this REPLACES the values with the new ones.
        """
        # Detect if user_id is integer or UUID
        profile_id = None
        try:
            profile_id = int(user_id)
        except (ValueError, TypeError):
            # It's a UUID, can't use it for student_id
            return
        
        client = await self._client()
        
        # First, try to fetch current values
        try:
            current_resp = await self._execute(
                client.table("user_scores")
                .select("*")
                .eq("student_id", profile_id)
                .execute(),
                op="user_scores.select"
            )
            current_data = getattr(current_resp, "data", None)
            
            if current_data and len(current_data) > 0:
                # Record exists, increment counters
                current = current_data[0]
                update_payload = {
                    "elo": elo,
                    "gpa": gpa,
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                    "total_completed_questions": (current.get("total_completed_questions") or 0) + questions_attempted,
                }
                
                # Only increment if we have new values
                if questions_attempted > 0 or questions_passed > 0:
                    # Increment questions_attempted if column exists
                    if "total_questions_attempted" in str(current):
                        update_payload["total_questions_attempted"] = (current.get("total_questions_attempted") or 0) + questions_attempted
                    # Increment questions_passed if column exists
                    if "total_questions_passed" in str(current):
                        update_payload["total_questions_passed"] = (current.get("total_questions_passed") or 0) + questions_passed
                
                if challenges_completed > 0:
                    if "total_challenges_completed" in str(current):
                        update_payload["total_challenges_completed"] = (current.get("total_challenges_completed") or 0) + challenges_completed
                
                if badges > 0:
                    if "total_badges" in str(current):
                        update_payload["total_badges"] = (current.get("total_badges") or 0) + badges
                
                # Calculate total_earned_elo as difference from base ELO (1000 or 1200)
                base_elo = 1000  # From table default
                update_payload["total_earned_elo"] = max(0, elo - base_elo)
                
                await self._execute(
                    client.table("user_scores")
                    .update(update_payload)
                    .eq("student_id", profile_id)
                    .execute(),
                    op="user_scores.update"
                )
            else:
                # No record exists, insert new one
                insert_payload = {
                    "student_id": profile_id,
                    "elo": elo,
                    "total_earned_elo": max(0, elo - 1000),  # Base ELO from table default
                    "gpa": gpa,
                    "total_completed_questions": questions_attempted,
                }
                
                # Only add fields if they have values
                if questions_attempted > 0:
                    insert_payload["total_questions_attempted"] = questions_attempted
                if questions_passed > 0:
                    insert_payload["total_questions_passed"] = questions_passed
                if challenges_completed > 0:
                    insert_payload["total_challenges_completed"] = challenges_completed
                if badges > 0:
                    insert_payload["total_badges"] = badges
                
                await self._execute(
                    client.table("user_scores").insert(insert_payload).execute(),
                    op="user_scores.insert"
                )
        except Exception as e:
            # Table might not exist yet, log and ignore
            import logging
            logging.getLogger("achievements.repository").debug(f"Failed to update user_scores: {e}")
            pass

    async def update_question_progress(
        self,
        user_id: str,
        question_id: str,
        challenge_id: str,
        attempt_id: str,
        tests_passed: int,
        tests_total: int,
        elo_earned: int,
        gpa_contribution: float,
    ) -> None:
        """Update or insert user_question_progress table with individual question results."""
        # Detect if user_id is integer or UUID
        profile_id = None
        try:
            profile_id = int(user_id)
        except (ValueError, TypeError):
            # It's a UUID, can't use it for profile_id
            return
        
        client = await self._client()
        
        try:
            # Check if record exists
            resp = await self._execute(
                client.table("user_question_progress")
                .select("*")
                .eq("profile_id", profile_id)
                .eq("question_id", question_id)
                .limit(1)
                .execute(),
                op="user_question_progress.check"
            )
            
            existing = getattr(resp, "data", [])
            is_completed = tests_passed >= tests_total
            
            if existing:
                # Update existing record
                existing_record = existing[0]
                update_payload = {
                    "tests_passed": max(tests_passed, existing_record.get("tests_passed", 0)),
                    "tests_total": tests_total,
                    "is_completed": is_completed or existing_record.get("is_completed", False),
                    "best_score": max(tests_passed, existing_record.get("best_score", 0)),
                    "elo_earned": existing_record.get("elo_earned", 0) + elo_earned,
                    "gpa_contribution": max(gpa_contribution, existing_record.get("gpa_contribution", 0)),
                    "last_attempted_at": datetime.now(timezone.utc).isoformat(),
                }
                await self._execute(
                    client.table("user_question_progress")
                    .update(update_payload)
                    .eq("id", existing_record["id"])
                    .execute(),
                    op="user_question_progress.update"
                )
            else:
                # Insert new record
                insert_payload = {
                    "profile_id": profile_id,
                    "question_id": question_id,
                    "challenge_id": challenge_id,
                    "attempt_id": attempt_id,
                    "tests_passed": tests_passed,
                    "tests_total": tests_total,
                    "is_completed": is_completed,
                    "best_score": tests_passed,
                    "elo_earned": elo_earned,
                    "gpa_contribution": gpa_contribution,
                }
                await self._execute(
                    client.table("user_question_progress").insert(insert_payload).execute(),
                    op="user_question_progress.insert"
                )
        except Exception as e:
            # Table might not exist yet, ignore silently
            pass

    # --- Titles -----------------------------------------------------------

    async def list_titles(self) -> List[Dict[str, Any]]:
        client = await self._client()
        query = client.table("titles").select("*")
        resp = await self._execute(query.execute(), op="titles.list")
        data = getattr(resp, "data", None)
        return data or []

    async def update_profile_title(self, user_id: str, title_id: Any) -> None:
        if title_id is None:
            return
        client = await self._client()
        query = client.table("profiles").update({"title_id": title_id}).eq("id", user_id)
        await self._execute(query.execute(), op="profiles.title_update")

    # --- Badges -----------------------------------------------------------

    async def list_badge_definitions(self) -> List[Dict[str, Any]]:
        client = await self._client()
        query = client.table("badges").select("*")
        resp = await self._execute(query.execute(), op="badges.list")
        data = getattr(resp, "data", None)
        return data or []

    async def get_badges_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        # Determine if user_id is an integer (profile_id) or UUID
        profile_id = None
        uuid_user_id = None
        try:
            profile_id = int(user_id)
        except (ValueError, TypeError):
            uuid_user_id = user_id
            
        client = await self._client()
        # Some deployments use `user_badges` table, others `user_badge` - try both.
        for table_name in ("user_badges", "user_badge"):
            try:
                # Try both profile_id and user_id columns
                if profile_id is not None:
                    query = (
                        client.table(table_name)
                        .select("*, badge:badges(*)")
                        .eq("profile_id", profile_id)
                        .order("date_earned", desc=True)
                        .execute()
                    )
                else:
                    query = (
                        client.table(table_name)
                        .select("*, badge:badges(*)")
                        .eq("user_id", uuid_user_id)
                        .order("date_earned", desc=True)
                        .execute()
                    )
            except Exception:
                continue
            resp = await self._execute(query, op=f"{table_name}.list")
            data = getattr(resp, "data", None)
            if data:
                # Normalize returned shape to always include badge key under `badge`
                normalized: List[Dict[str, Any]] = []
                for row in data:
                    if isinstance(row, dict):
                        # compatibility: some rows include `badges` or nested `badge`
                        if "badges" in row and "badge" not in row:
                            row["badge"] = row.get("badges")
                        normalized.append(row)
                return normalized
        return []

    async def add_badge_to_user(
        self,
        user_id: str,
        badge_id: Any,
        challenge_id: Optional[str] = None,
        attempt_id: Optional[str] = None,
        source_submission_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        # Determine if user_id is an integer (profile_id) or UUID
        profile_id = None
        uuid_user_id = None
        try:
            profile_id = int(user_id)
        except (ValueError, TypeError):
            uuid_user_id = user_id
            
        payload: Dict[str, Any] = {
            "badge_id": badge_id,
        }
        
        # Set both profile_id and user_id for compatibility
        if profile_id is not None:
            payload["profile_id"] = profile_id
        if uuid_user_id is not None:
            payload["user_id"] = uuid_user_id
            
        if challenge_id is not None:
            payload["challenge_id"] = challenge_id
        if attempt_id is not None:
            payload["challenge_attempt_id"] = attempt_id
        if source_submission_id is not None:
            payload["source_submission_id"] = source_submission_id
        ts = datetime.now(timezone.utc).isoformat()
        payload.setdefault("awarded_at", ts)
        payload.setdefault("date_earned", ts)
        client = await self._client()
        # Try inserting into either user_badges or user_badge depending on schema
        for table_name in ("user_badges", "user_badge"):
            try:
                query = client.table(table_name).insert(payload)
            except Exception:
                continue
            resp = await self._execute(query.execute(), op=f"{table_name}.insert")
            data = getattr(resp, "data", None)
            if data:
                return data[0] if isinstance(data, list) else data
        return None
        return None

    async def add_badges_batch(
        self,
        user_id: str,
        badge_ids: Iterable[Any],
        challenge_id: Optional[str],
        attempt_id: Optional[str],
        source_submission_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        payloads: List[Dict[str, Any]] = []
        now_iso = datetime.now(timezone.utc).isoformat()
        for badge_id in badge_ids:
            payload: Dict[str, Any] = {
                "user_id": user_id,
                "badge_id": badge_id,
                "date_earned": now_iso,
                "awarded_at": now_iso,
            }
            if challenge_id is not None:
                payload["challenge_id"] = challenge_id
            if attempt_id is not None:
                payload["challenge_attempt_id"] = attempt_id
            if source_submission_id is not None:
                payload["source_submission_id"] = source_submission_id
            payloads.append(payload)
        if not payloads:
            return []
        client = await self._client()
        # Try batch insert into both possible table names
        for table_name in ("user_badges", "user_badge"):
            try:
                query = client.table(table_name).insert(payloads)
            except Exception:
                continue
            resp = await self._execute(query.execute(), op=f"{table_name}.batch_insert")
            data = getattr(resp, "data", None)
            if isinstance(data, list) and data:
                return data
        # Fallback: try inserting one-by-one
        inserted: List[Dict[str, Any]] = []
        for p in payloads:
            row = await self.add_badge_to_user(
                p.get("user_id"), p.get("badge_id"), p.get("challenge_id"), p.get("challenge_attempt_id"), p.get("source_submission_id")
            )
            if row:
                inserted.append(row)
        return inserted


achievements_repository = AchievementsRepository()

__all__ = ["achievements_repository", "AchievementsRepository", "_parse_datetime"]
