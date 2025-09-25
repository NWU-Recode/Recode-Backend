from __future__ import annotations
from typing import Dict\nfrom datetime import datetime, timezone\n\nfrom .repository import challenge_repository\nfrom .schemas import ChallengeSubmitRequest, ChallengeSubmitResponse
from app.features.submissions.service import submissions_service\nfrom app.features.achievements.service import achievements_service\nfrom app.features.achievements.schemas import CheckAchievementsRequest\n

class ChallengeService:\n    def _time_limit_for_tier(self, tier: str | None) -> int | None:
        limits = {
            "base": 3600,
            "plain": 3600,
            "common": 3600,
            "ruby": 5400,
            "emerald": 7200,
            "diamond": 10800,
        }
        key = (tier or "base").lower()
        return limits.get(key, limits.get("base"))

    def _parse_ts(self, value) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None

    async def submit(self, req: ChallengeSubmitRequest, user_id: str, user_role: str = "student") -> ChallengeSubmitResponse:
        if user_role != "student":
            raise ValueError("only_students_scored")

        challenge = await challenge_repository.get_challenge(str(req.challenge_id))
        if not challenge:
            raise ValueError("challenge_not_found")
        tier = str(challenge.get("tier") or "base").lower()

        try:
            student_number = int(user_id)
        except Exception:
            raise ValueError("invalid_student_number")

        attempt = await challenge_repository.create_or_get_open_attempt(str(req.challenge_id), student_number)
        if attempt.get("status") == "submitted":
            raise ValueError("challenge_already_submitted")

        snapshot = await challenge_repository.get_snapshot(attempt)
        if not snapshot:
            raise ValueError("challenge_snapshot_missing")

        snapshot_map: Dict[str, Dict] = {str(s["question_id"]): s for s in snapshot}
        language_overrides: Dict[str, int] = {
            qid: int(data.get("language_id") or 71) for qid, data in snapshot_map.items()
        }
        weight_overrides: Dict[str, int] = {
            qid: int(data.get("points") or 0) for qid, data in snapshot_map.items()
        }

        submissions_map: Dict[str, str] = {}
        for item in req.items or []:
            qid = str(item.question_id)
            if qid in snapshot_map:
                submissions_map[qid] = item.source_code

        grading = await submissions_service.grade_challenge_submission(
            challenge_id=str(req.challenge_id),
            attempt_id=str(attempt.get("id")),
            submissions=submissions_map,
            language_overrides=language_overrides,
            question_weights=weight_overrides,
        )

        started_dt = self._parse_ts(attempt.get("started_at"))
        finished_dt = datetime.now(timezone.utc)
        duration_seconds = int(max(0, (finished_dt - started_dt).total_seconds())) if started_dt else None
        time_limit_seconds = self._time_limit_for_tier(tier)
        grading = grading.model_copy(
            update={
                "time_used_seconds": duration_seconds,
                "time_limit_seconds": time_limit_seconds,
            }
        )

        updated_attempt = await challenge_repository.finalize_attempt(
            str(attempt["id"]),
            score=grading.gpa_score,
            correct_count=len(grading.passed_questions),
            duration_seconds=duration_seconds,
            tests_total=grading.tests_total,
            tests_passed=grading.tests_passed_total,
            elo_delta=grading.elo_delta,
            efficiency_bonus=grading.efficiency_bonus_total,
        )

        submission_id = str(updated_attempt.get("id", attempt.get("id")))
        performance_payload = {
            "time_used_seconds": duration_seconds,
            "time_limit_seconds": time_limit_seconds,
            "tests_total": grading.tests_total,
            "tests_passed_total": grading.tests_passed_total,
            "average_execution_time_ms": grading.average_execution_time_ms,
            "average_memory_used_kb": grading.average_memory_used_kb,
            "base_elo_total": grading.base_elo_total,
            "efficiency_bonus_total": grading.efficiency_bonus_total,
        }
        performance_payload = {k: v for k, v in performance_payload.items() if v is not None}
        await achievements_service.check_achievements(
            user_id,
            CheckAchievementsRequest(
                submission_id=submission_id,
                elo_delta_override=int(grading.elo_delta),
                badge_tiers=grading.badge_tiers_awarded,
                performance=performance_payload,
            ),
        )

        return ChallengeSubmitResponse(
            challenge_attempt_id=submission_id,
            challenge_id=str(req.challenge_id),
            status=str(updated_attempt.get("status", "submitted")),
            gpa_score=int(grading.gpa_score),
            gpa_max_score=int(grading.gpa_max_score),
            elo_delta=int(grading.elo_delta),
            base_elo_total=int(grading.base_elo_total),
            efficiency_bonus_total=int(grading.efficiency_bonus_total),
            tests_total=int(grading.tests_total),
            tests_passed_total=int(grading.tests_passed_total),
            time_used_seconds=grading.time_used_seconds,
            time_limit_seconds=grading.time_limit_seconds,
            average_execution_time_ms=grading.average_execution_time_ms,
            average_memory_used_kb=grading.average_memory_used_kb,
            badge_tiers_awarded=grading.badge_tiers_awarded,
            passed_question_ids=[qid for qid in grading.passed_questions],
            failed_question_ids=[qid for qid in grading.failed_questions],
            missing_question_ids=[qid for qid in grading.missing_questions],
            question_results=grading.question_results,
        )

challenge_service = ChallengeService()



