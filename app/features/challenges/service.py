from __future__ import annotations
from typing import Dict, Any, List
from .repository import challenge_repository
from .schemas import ChallengeSubmitRequest, ChallengeSubmitResponse
from app.features.questions.repository import question_repository
from app.features.judge0.schemas import CodeSubmissionCreate
from app.features.judge0.service import judge0_service
from app.features.challenges.scoring import (
    AttemptScore,
    Tier,
    recompute_semester_mark,
    summarize,
    determine_milestones,
)

class ChallengeService:
    async def submit(self, req: ChallengeSubmitRequest, user_id: str, user_role: str = "student") -> ChallengeSubmitResponse:
        if user_role != "student":
            raise ValueError("only_students_scored")
        challenge = await challenge_repository.get_challenge(str(req.challenge_id))
        if not challenge:
            raise ValueError("Challenge not found")
        attempt = await challenge_repository.create_or_get_open_attempt(str(req.challenge_id), user_id)
        if attempt.get("status") == "submitted":
            raise ValueError("challenge_already_submitted")
        snapshot = await challenge_repository.get_snapshot(attempt)
        snapshot_ids = [s["question_id"] for s in snapshot]
        latest_attempts = await question_repository.list_latest_attempts_for_challenge(str(req.challenge_id), user_id)
        attempts_by_qid = {str(a.get("question_id")): a for a in latest_attempts if str(a.get("question_id")) in snapshot_ids}
        missing_qids = [qid for qid in snapshot_ids if qid not in attempts_by_qid]
        # Optionally batch fill missing if code provided
        if missing_qids and req.items:
            run_items = [i for i in req.items if str(i.question_id) in missing_qids]
            if run_items:
                ordered: List[str] = []
                batch_submissions: List[CodeSubmissionCreate] = []
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
        if missing_qids:
            raise ValueError(f"missing_questions:{','.join(missing_qids)}")
        passed_ids: List[str] = []
        failed_ids: List[str] = []
        attempt_scores: List[AttemptScore] = []
        for qid in snapshot_ids:
            att = attempts_by_qid.get(qid)
            correct = bool(att and att.get("is_correct"))
            if correct:
                passed_ids.append(qid)
            else:
                failed_ids.append(qid)
            # derive tier from snapshot meta if present else default bronze
            meta = next((s for s in snapshot if s["question_id"] == qid), None)
            tier_raw = (meta or {}).get("tier", "bronze").lower()
            tier = Tier(tier_raw) if tier_raw in Tier._value2member_map_ else Tier.bronze
            attempt_scores.append(AttemptScore(tier=tier, correct=correct))
        correct_count = len(passed_ids)
        score = correct_count
        finalized = await challenge_repository.finalize_attempt(attempt["id"], score, correct_count)
        # milestone detection (placeholder plain count lookups)
        plain_completed = await challenge_repository.count_plain_completed(user_id)
        total_plain_planned = await challenge_repository.total_plain_planned()
        unlocks = determine_milestones(plain_completed, total_plain_planned)
        agg = recompute_semester_mark(
            plain_attempts=attempt_scores,
            ruby_correct=unlocks.ruby and any(a.tier == Tier.ruby and a.correct for a in attempt_scores),
            emerald_correct=unlocks.emerald and any(a.tier == Tier.emerald and a.correct for a in attempt_scores),
            diamond_correct=unlocks.diamond and any(a.tier == Tier.diamond and a.correct for a in attempt_scores),
        )
        breakdown = summarize(agg)
        # Persist (idempotent upsert) into progress table (pseudo - implement repository later)
        # await progress_repository.upsert_student_progress(user_id, breakdown)
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
