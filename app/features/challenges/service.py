from __future__ import annotations
from typing import Dict

from .repository import challenge_repository
from .schemas import ChallengeSubmitRequest, ChallengeSubmitResponse
from app.features.submissions.service import submissions_service


class ChallengeService:
    async def submit(self, req: ChallengeSubmitRequest, user_id: str, user_role: str = "student") -> ChallengeSubmitResponse:
        if user_role != "student":
            raise ValueError("only_students_scored")

        challenge = await challenge_repository.get_challenge(str(req.challenge_id))
        if not challenge:
            raise ValueError("challenge_not_found")

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

        updated_attempt = await challenge_repository.finalize_attempt(
            str(attempt["id"]),
            score=grading.gpa_score,
            correct_count=len(grading.passed_questions),
        )

        return ChallengeSubmitResponse(
            challenge_attempt_id=str(updated_attempt.get("id", attempt.get("id"))),
            challenge_id=str(req.challenge_id),
            status=str(updated_attempt.get("status", "submitted")),
            gpa_score=int(grading.gpa_score),
            gpa_max_score=int(grading.gpa_max_score),
            elo_delta=int(grading.elo_delta),
            passed_question_ids=[qid for qid in grading.passed_questions],
            failed_question_ids=[qid for qid in grading.failed_questions],
            missing_question_ids=[qid for qid in grading.missing_questions],
            question_results=grading.question_results,
        )

challenge_service = ChallengeService()
