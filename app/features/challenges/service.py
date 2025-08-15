from __future__ import annotations
from typing import Dict, Any
from .repository import challenge_repository
from .schemas import ChallengeSubmitRequest, ChallengeSubmitResponse
from app.features.questions.repository import question_repository
from app.features.judge0.schemas import CodeSubmissionCreate
from app.features.judge0.service import judge0_service

class ChallengeService:
    async def submit(self, req: ChallengeSubmitRequest, user_id: str) -> ChallengeSubmitResponse:
        challenge = await challenge_repository.get_challenge(str(req.challenge_id))
        if not challenge:
            raise ValueError("Challenge not found")
        attempt = await challenge_repository.create_or_get_open_attempt(str(req.challenge_id), user_id)
        if attempt.get("status") == "submitted":
            raise ValueError("challenge_already_submitted")
        snapshot = await challenge_repository.get_snapshot(attempt)
        snapshot_ids = [s["question_id"] for s in snapshot]
        # Latest attempts by question
        latest_attempts = await question_repository.list_latest_attempts_for_challenge(str(req.challenge_id), user_id)
        attempts_by_qid = {str(a.get("question_id")): a for a in latest_attempts if str(a.get("question_id")) in snapshot_ids}
        missing_qids = [qid for qid in snapshot_ids if qid not in attempts_by_qid]
        # Optionally batch fill missing if code provided
        if missing_qids and req.items:
            run_items = [i for i in req.items if str(i.question_id) in missing_qids]
            if run_items:
                ordered: list[str] = []
                batch_submissions: list[CodeSubmissionCreate] = []
                snap_map = {s["question_id"]: s for s in snapshot}
                for item in run_items:
                    qid = str(item.question_id)
                    if qid not in snap_map:
                        continue
                    meta = snap_map[qid]
                    batch_submissions.append(CodeSubmissionCreate(
                        source_code=item.source_code,
                        language_id=meta["language_id"],
                        stdin=item.stdin,
                        expected_output=meta.get("expected_output"),
                    ))
                    ordered.append(qid)
                if batch_submissions:
                    batch_results = await judge0_service.execute_batch(batch_submissions)
                    for (token, exec_res), qid in zip(batch_results, ordered):
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
                    latest_attempts = await question_repository.list_latest_attempts_for_challenge(str(req.challenge_id), user_id)
                    attempts_by_qid = {str(a.get("question_id")): a for a in latest_attempts if str(a.get("question_id")) in snapshot_ids}
                    missing_qids = [qid for qid in snapshot_ids if qid not in attempts_by_qid]
        # If still missing after attempt to fill, return 400 semantics via raise
        if missing_qids:
            raise ValueError(f"missing_questions:{','.join(missing_qids)}")
        passed_ids: list[str] = []
        failed_ids: list[str] = []
        for qid in snapshot_ids:
            att = attempts_by_qid.get(qid)
            if att and att.get("is_correct"):
                passed_ids.append(qid)
            else:
                failed_ids.append(qid)
        correct_count = len(passed_ids)
        score = correct_count
        finalized = await challenge_repository.finalize_attempt(attempt["id"], score, correct_count)
        return ChallengeSubmitResponse(
            challenge_attempt_id=finalized["id"],
            score=score,
            correct_count=correct_count,
            status=finalized.get("status", "submitted"),
            snapshot_question_ids=[qid for qid in snapshot_ids],
            passed_ids=[qid for qid in passed_ids],
            failed_ids=[qid for qid in failed_ids],
            missing_question_ids=None,
        )

challenge_service = ChallengeService()
