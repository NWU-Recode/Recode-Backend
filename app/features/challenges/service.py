from __future__ import annotations
from typing import Dict, Any
from .repository import challenge_repository
from .schemas import ChallengeSubmitRequest, ChallengeSubmitResponse
from app.features.questions.repository import question_repository
from app.features.judge0.schemas import CodeSubmissionCreate
from app.features.judge0.service import judge0_service

class ChallengeService:
    async def finalize(self, req: ChallengeSubmitRequest, user_id: str) -> ChallengeSubmitResponse:
        challenge = await challenge_repository.get_challenge(str(req.challenge_id))
        if not challenge:
            raise ValueError("Challenge not found")
        attempt = await challenge_repository.get_open_attempt(str(req.challenge_id), user_id)
        if not attempt:
            attempt = await challenge_repository.start_attempt(str(req.challenge_id), user_id)
        # Gather latest attempts for this challenge
        attempts = await question_repository.list_latest_attempts_for_challenge(str(req.challenge_id), user_id)
        # Fetch questions to compute potential score & detect missing
        all_questions = await challenge_repository.get_challenge_questions(str(req.challenge_id))
        question_map = {str(q["id"]): q for q in all_questions}
        question_points_map = {str(q["id"]): q.get("points", 0) for q in all_questions}
        attempted_ids = {str(a.get("question_id")) for a in attempts}
        missing_question_ids = [qid for qid in question_points_map.keys() if qid not in attempted_ids]
        # Optional fallback execute for provided items covering missing questions
        if req.items and missing_question_ids:
            # Filter request items to only those still missing
            run_items = [item for item in req.items if str(item.question_id) in missing_question_ids]
            batch_submissions: list[CodeSubmissionCreate] = []
            ordered_qids: list[str] = []
            for item in run_items:
                qid = str(item.question_id)
                qrow = question_map[qid]
                batch_submissions.append(CodeSubmissionCreate(
                    source_code=item.source_code,
                    language_id=qrow["language_id"],
                    stdin=item.stdin,
                    expected_output=qrow.get("expected_output"),
                ))
                ordered_qids.append(qid)
            if batch_submissions:
                batch_results = await judge0_service.execute_batch(batch_submissions)
                for (token, exec_res), qid in zip(batch_results, ordered_qids):
                    await question_repository.upsert_attempt({
                        "question_id": qid,
                        "challenge_id": str(req.challenge_id),
                        "user_id": user_id,
                        "judge0_token": token,
                        "source_code": next(i.source_code for i in run_items if str(i.question_id) == qid),
                        "stdout": exec_res.stdout,
                        "stderr": exec_res.stderr,
                        "status_id": exec_res.status_id,
                        "status_description": exec_res.status_description,
                        "time": exec_res.execution_time,
                        "memory": exec_res.memory_used,
                        "is_correct": exec_res.success,
                        "latest": True,
                    })
                # Refresh attempts after fallback executions
                attempts = await question_repository.list_latest_attempts_for_challenge(str(req.challenge_id), user_id)
                attempted_ids = {str(a.get("question_id")) for a in attempts}
                missing_question_ids = [qid for qid in question_points_map.keys() if qid not in attempted_ids]
        # Score is sum of points for correct attempts
        correct = [a for a in attempts if a.get("is_correct")]
        score = sum(question_points_map.get(str(a.get("question_id")), 0) for a in correct)
        correct_count = len(correct)
        finalized = await challenge_repository.finalize_attempt(attempt["id"], score, correct_count)
        return ChallengeSubmitResponse(
            challenge_attempt_id=finalized["id"],
            score=finalized.get("score", 0),
            correct_count=finalized.get("correct_count", correct_count),
            status=finalized.get("status", "completed"),
            missing_question_ids=[qid for qid in missing_question_ids],
        )

challenge_service = ChallengeService()
