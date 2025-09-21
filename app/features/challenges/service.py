from __future__ import annotations
from typing import Dict, Any, List
from .repository import challenge_repository
from .schemas import ChallengeSubmitRequest, ChallengeSubmitResponse
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
    async def _list_latest_attempts_for_challenge(self, challenge_id: str, user_id: str) -> List[Dict[str, Any]]:
        # Fetch latest attempts per question from Supabase questions_attempts table if exists
        try:
            from app.DB.supabase import get_supabase
            client = await get_supabase()
            # Expect a DB function latest_attempts_for_challenge; if missing, return empty
            resp = client.rpc("latest_attempts_for_challenge", {"challenge_id": challenge_id, "user_id": user_id}).execute()
            return resp.data or []
        except Exception:
            return []

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
        latest_attempts = await self._list_latest_attempts_for_challenge(str(req.challenge_id), user_id)
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
                    ordered.append(qid)
                    snap = snap_map[qid]
                    batch_submissions.append(CodeSubmissionCreate(
                        source_code=item.source_code,
                        language_id=int(snap.get("language_id") or 71),
                        expected_output=str(snap.get("expected_output") or ""),
                        max_time_ms=int(snap.get("max_time_ms") or 2000),
                        max_memory_kb=int(snap.get("max_memory_kb") or 256000),
                        stdin=item.stdin,
                    ))
                if batch_submissions:
                    results = await judge0_service.execute_batch(batch_submissions)  # type: ignore
                    for (token, res), qid in zip(results, ordered):
                        attempts_by_qid[qid] = {
                            "question_id": qid,
                            "is_correct": bool(res.success),
                            "judge0_token": token,
                        }
        passed = sum(1 for a in attempts_by_qid.values() if a.get("is_correct"))
        score = summarize([AttemptScore(points=1, passed=a.get("is_correct", False)) for a in attempts_by_qid.values()])
        await challenge_repository.finalize_attempt(str(attempt["id"]), score=score.score, correct_count=passed)
        return ChallengeSubmitResponse(challenge_attempt_id=str(attempt["id"]), score=score.score, correct=passed)

challenge_service = ChallengeService()
