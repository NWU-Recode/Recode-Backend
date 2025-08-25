from __future__ import annotations
from typing import Optional, Dict, Any, List
from .repository import question_repository
from .schemas import (
    ExecuteRequest, ExecuteResponse,
    QuestionSubmitRequest, QuestionSubmitResponse,
    BatchExecuteRequest, BatchExecuteResponse, BatchExecuteItemResponse,
    BatchSubmitRequest, BatchSubmitResponse, BatchSubmitItemResponse,
    ChallengeTilesResponse, TileItem
)
import hashlib
from fastapi import HTTPException
from app.features.judge0.schemas import CodeSubmissionCreate
from app.features.judge0.service import judge0_service
from app.features.challenges.repository import challenge_repository
from app.db.supabase import get_supabase
from app.features.questions.grading import map_app_status
from app.common.quota import enforce_source_stdin, QuotaError
from app.features.submissions.service import submission_service
from app.features.submissions.schemas import SubmissionCreate
import asyncio, time

class QuestionService:
    # ---- Helpers ----
    @staticmethod
    def _map_app_status(status_id: int, is_correct: Optional[bool]) -> str:  # backward compat wrapper
        return map_app_status(status_id, is_correct)

    async def _ensure_snapshot_membership(self, question_id: str, challenge_id: str, user_id: str):
        attempt = await challenge_repository.create_or_get_open_attempt(challenge_id, user_id)
        snapshot = attempt.get("snapshot_questions") or []
        ids = {q["question_id"] for q in snapshot}
        if question_id not in ids:
            raise ValueError("invalid_question: not in snapshot for attempt")
        # Enforce status & deadline
        status = attempt.get("status")
        if status == "submitted":
            raise ValueError("challenge_already_submitted")
        if status == "expired":
            raise ValueError("challenge_expired")
        deadline_at = attempt.get("deadline_at")
        if deadline_at:
            from datetime import datetime, timezone
            try:
                dt = datetime.fromisoformat(str(deadline_at).replace("Z", "+00:00"))
                if datetime.now(timezone.utc) > dt:
                    raise ValueError("challenge_expired")
            except ValueError:
                pass
        return attempt, snapshot

    async def execute(self, req: ExecuteRequest, user_id: str) -> ExecuteResponse:
        try:
            enforce_source_stdin(req.source_code, req.stdin)
        except QuotaError as qe:
            raise ValueError(str(qe))
        q = await question_repository.get_question(str(req.question_id))
        if not q:
            raise ValueError("question_not_found")
        await self._ensure_snapshot_membership(str(req.question_id), str(q["challenge_id"]), user_id)
        hasher = hashlib.sha256()
        composite = f"{q['language_id']}\n{req.stdin or ''}\n{req.source_code}\n{q.get('expected_output') or ''}".encode()
        hasher.update(composite)
        code_hash = hasher.hexdigest()
        cached = await question_repository.find_by_code_hash(str(req.question_id), user_id, code_hash)
        if cached and cached.get("is_correct") is not None:
            return ExecuteResponse(
                judge0_token=cached.get("judge0_token", ""),
                stdout=cached.get("stdout"),
                stderr=cached.get("stderr"),
                status_id=cached.get("status_id", -1),
                status_description=cached.get("status_description", "cached"),
                is_correct=None,
                time=cached.get("time"),
                memory=cached.get("memory"),
            )
        submission = CodeSubmissionCreate(
            source_code=req.source_code,
            language_id=q["language_id"],
            stdin=req.stdin,
            expected_output=None
        )
        token, result = await judge0_service.execute_code_sync(submission)  # waited
        return ExecuteResponse(
            judge0_token=token,
            stdout=result.stdout,
            stderr=result.stderr,
            status_id=result.status_id,
            status_description=result.status_description,
            is_correct=None,
            time=result.execution_time,
            memory=result.memory_used,
        )

    async def submit(self, req: QuestionSubmitRequest, user_id: str) -> QuestionSubmitResponse:
        try:
            enforce_source_stdin(req.source_code, req.stdin)
        except QuotaError as qe:
            raise ValueError(str(qe))
        if not req.idempotency_key:
            raise ValueError("idempotency_key_required")
        q = await question_repository.get_question(str(req.question_id))
        if not q:
            raise ValueError("question_not_found")
        attempt, snapshot = await self._ensure_snapshot_membership(str(req.question_id), str(q["challenge_id"]), user_id)
        # Build hash including attempt id for reuse specificity
        hasher = hashlib.sha256()
        composite = f"{q['language_id']}\n{req.stdin or ''}\n{req.source_code}\n{attempt['id']}".encode()
        hasher.update(composite)
        code_hash = hasher.hexdigest()
        # Idempotent replay
        existing_idem = await question_repository.find_by_idempotency_key(str(req.question_id), user_id, req.idempotency_key)
        if existing_idem:
            # Spec: duplicate idempotency key should raise conflict (409)
            raise ValueError("duplicate_idempotency_key")
        # Reuse by code hash
        cached = await question_repository.find_by_code_hash(str(req.question_id), user_id, code_hash)
        if cached and cached.get("is_correct") is not None:
            app_status = self._map_app_status(cached.get("status_id", -1), cached.get("is_correct"))
            return QuestionSubmitResponse(
                question_attempt_id=cached["id"],
                challenge_attempt_id=attempt["id"],
                token=cached.get("judge0_token", ""),
                app_status=app_status,
                is_correct=cached.get("is_correct", False),
                stdout=cached.get("stdout"),
                stderr=cached.get("stderr"),
                status_id=cached.get("status_id", -1),
                status_description=cached.get("status_description", "cached"),
                time=cached.get("time"),
                memory=cached.get("memory"),
                points_awarded=(1 if cached.get("is_correct") else 0),
                hash=cached.get("code_hash") or cached.get("hash"),
            )
        # Async submit (wait=false) then poll up to 45s for terminal state
        submission = CodeSubmissionCreate(
            source_code=req.source_code,
            language_id=q["language_id"],
            stdin=req.stdin,
            expected_output=q.get("expected_output")
        )
        token_resp = await judge0_service.submit_code(submission)
        token = token_resp.token  # type: ignore
        start = time.time()
        poll_interval = 1.0
        result = None
        while time.time() - start < 45:
            raw = await judge0_service.get_submission_result(token)
            status_id = raw.status.get("id") if raw.status else None
            if status_id not in [1, 2]:
                # Terminal
                result = judge0_service._to_code_execution_result(raw, submission.expected_output, submission.language_id)
                break
            await asyncio.sleep(poll_interval)
        if result is None:
            # Pending path: persist submission row only (processing) and return 202 envelope sentinel
            sub_create = SubmissionCreate(
                source_code=submission.source_code,
                language_id=submission.language_id,
                stdin=submission.stdin,
                expected_output=submission.expected_output,
                question_id=str(req.question_id),
            )
            await submission_service.store_submission(sub_create, user_id, token)
            return {"__pending__": True, "token": token, "question_id": str(req.question_id), "challenge_attempt_id": attempt["id"], "hash": code_hash}
        # Terminal: persist attempt & submission/result
        is_correct = result.success
        app_status = self._map_app_status(result.status_id, is_correct)
        # Persist submission & result (idempotent if exists)
        sub_create = SubmissionCreate(
            source_code=submission.source_code,
            language_id=submission.language_id,
            stdin=submission.stdin,
            expected_output=submission.expected_output,
            question_id=str(req.question_id),
        )
        try:
            await submission_service.store_submission(sub_create, user_id, token)
        except Exception:
            pass
        try:
            from app.features.judge0.schemas import CodeExecutionResult as CER
            await submission_service.store_result(token, result)  # type: ignore[arg-type]
        except Exception:
            pass
        existing_latest = await question_repository.get_existing_attempt(str(req.question_id), user_id)
        payload = {
            "question_id": str(req.question_id),
            "challenge_id": str(q["challenge_id"]),
            "challenge_attempt_id": attempt["id"],
            "user_id": user_id,
            "judge0_token": token,
            "source_code": req.source_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "status_id": result.status_id,
            "status_description": result.status_description,
            "time": result.execution_time,
            "memory": result.memory_used,
            "is_correct": is_correct,
            "code_hash": code_hash,
            "hash": code_hash,
            "idempotency_key": req.idempotency_key,
            "latest": True,
        }
        if existing_latest:
            await question_repository.mark_previous_not_latest(str(req.question_id), user_id)
            payload["id"] = existing_latest["id"]
        stored = await question_repository.upsert_attempt(payload)
        return QuestionSubmitResponse(
            question_attempt_id=stored["id"],
            challenge_attempt_id=attempt["id"],
            token=token,
            app_status=app_status,
            is_correct=is_correct,
            stdout=result.stdout,
            stderr=result.stderr,
            status_id=result.status_id,
            status_description=result.status_description,
            time=result.execution_time,
            memory=result.memory_used,
            points_awarded=(1 if is_correct else 0),
            hash=code_hash,
        )

    async def batch_execute(self, req: BatchExecuteRequest, user_id: str) -> BatchExecuteResponse:
        # Fetch all questions referenced for validation and expected outputs
        question_map = {}
        for item in req.items:
            q = await question_repository.get_question(str(item.question_id))
            if not q:
                raise ValueError(f"Question {item.question_id} not found")
            if str(q["challenge_id"]) != str(req.challenge_id):
                raise ValueError(f"Question {item.question_id} not in challenge {req.challenge_id}")
            question_map[str(item.question_id)] = q
        submissions = []
        order_keys = []
        for item in req.items:
            q = question_map[str(item.question_id)]
            submissions.append(CodeSubmissionCreate(
                source_code=item.source_code,
                language_id=q["language_id"],
                stdin=item.stdin,
                expected_output=q.get("expected_output")
            ))
            order_keys.append(str(item.question_id))
        batch_results = await judge0_service.execute_batch(submissions)  # returns list[(token, CodeExecutionResult)]
        responses: list[BatchExecuteItemResponse] = []
        for (token, exec_result), question_id in zip(batch_results, order_keys):
            q = question_map[question_id]
            is_correct = exec_result.success if q.get("expected_output") else None
            points = q.get("points") if is_correct else 0 if is_correct is not None else None
            responses.append(BatchExecuteItemResponse(
                question_id=question_id,
                judge0_token=token,
                is_correct=is_correct,
                stdout=exec_result.stdout,
                stderr=exec_result.stderr,
                status_id=exec_result.status_id,
                status_description=exec_result.status_description,
                time=exec_result.execution_time,
                memory=exec_result.memory_used,
                points_awarded=points,
            ))
        return BatchExecuteResponse(items=responses)

    async def batch_submit(self, req: BatchSubmitRequest, user_id: str) -> BatchSubmitResponse:
        # Ensure open challenge attempt exists for user/challenge
        attempt = await challenge_repository.get_open_attempt(str(req.challenge_id), user_id)
        if not attempt:
            attempt = await challenge_repository.start_attempt(str(req.challenge_id), user_id)
        question_map: dict[str, Any] = {}
        for item in req.items:
            q = await question_repository.get_question(str(item.question_id))
            if not q:
                raise ValueError(f"Question {item.question_id} not found")
            if str(q["challenge_id"]) != str(req.challenge_id):
                raise ValueError(f"Question {item.question_id} not in challenge {req.challenge_id}")
            question_map[str(item.question_id)] = q
        # Determine which questions still need graded attempts
        to_run_items = []
        skipped_existing: dict[str, Any] = {}
        for item in req.items:
            existing = await question_repository.get_existing_attempt(str(item.question_id), user_id)
            if existing and existing.get("is_correct") is not None:
                skipped_existing[str(item.question_id)] = existing
            else:
                to_run_items.append(item)
        submissions = []
        order_keys = []
        for item in to_run_items:
            q = question_map[str(item.question_id)]
            submissions.append(CodeSubmissionCreate(
                source_code=item.source_code,
                language_id=q["language_id"],
                stdin=item.stdin,
                expected_output=q.get("expected_output")
            ))
            order_keys.append(str(item.question_id))
        batch_results = []
        if submissions:
            batch_results = await judge0_service.execute_batch(submissions)
        responses: list[BatchSubmitItemResponse] = []
        # Persist newly executed
        for (token, exec_result), question_id in zip(batch_results, order_keys):
            q = question_map[question_id]
            is_correct = exec_result.success
            # Code hash
            hasher = hashlib.sha256()
            src = next(i.source_code for i in to_run_items if str(i.question_id) == question_id)
            stdin_val = next(i.stdin for i in to_run_items if str(i.question_id) == question_id)
            composite = f"{q['language_id']}\n{stdin_val or ''}\n{src}\n{attempt['id']}".encode()
            hasher.update(composite)
            code_hash = hasher.hexdigest()
            existing_latest = await question_repository.get_existing_attempt(question_id, user_id)
            payload = {
                "question_id": question_id,
                "challenge_id": str(req.challenge_id),
                "user_id": user_id,
                "judge0_token": token,
                "source_code": src,
                "stdout": exec_result.stdout,
                "stderr": exec_result.stderr,
                "status_id": exec_result.status_id,
                "status_description": exec_result.status_description,
                "time": exec_result.execution_time,
                "memory": exec_result.memory_used,
                "is_correct": is_correct,
                "code_hash": code_hash,
                "latest": True,
            }
            if existing_latest:
                await question_repository.mark_previous_not_latest(question_id, user_id)
                payload["id"] = existing_latest["id"]
            stored = await question_repository.upsert_attempt(payload)
            points_awarded = 1 if is_correct else 0
            app_status = self._map_app_status(exec_result.status_id, is_correct)
            responses.append(BatchSubmitItemResponse(
                question_id=question_id,
                question_attempt_id=stored["id"],
                token=token,
                app_status=app_status,
                is_correct=is_correct,
                stdout=exec_result.stdout,
                stderr=exec_result.stderr,
                status_id=exec_result.status_id,
                status_description=exec_result.status_description,
                time=exec_result.execution_time,
                memory=exec_result.memory_used,
                points_awarded=points_awarded or 0,
            ))
        # Add skipped existing attempts to response list
        for qid, existing in skipped_existing.items():
            q = question_map[qid]
            points_awarded = 1 if existing.get("is_correct") else 0
            app_status = self._map_app_status(existing.get("status_id", -1), existing.get("is_correct"))
            responses.append(BatchSubmitItemResponse(
                question_id=qid,
                question_attempt_id=existing["id"],
                token=existing.get("judge0_token", ""),
                app_status=app_status,
                is_correct=existing.get("is_correct", False),
                stdout=existing.get("stdout"),
                stderr=existing.get("stderr"),
                status_id=existing.get("status_id", -1),
                status_description=existing.get("status_description", "cached"),
                time=existing.get("time"),
                memory=existing.get("memory"),
                points_awarded=points_awarded or 0,
            ))
        return BatchSubmitResponse(items=responses)

    async def get_tiles(self, challenge_id: str, user_id: str) -> ChallengeTilesResponse:
        attempt = await challenge_repository.create_or_get_open_attempt(challenge_id, user_id)
        snapshot = attempt.get("snapshot_questions") or []
        latest_attempts = await question_repository.list_latest_attempts_for_challenge(challenge_id, user_id)
        index: Dict[str, Any] = {a.get("question_id"): a for a in latest_attempts}
        items: List[TileItem] = []
        for snap in snapshot:
            qid = snap["question_id"]
            existing = index.get(qid)
            if not existing:
                items.append(TileItem(question_id=qid, status="unattempted"))
            else:
                status = "passed" if existing.get("is_correct") else "failed"
                items.append(TileItem(
                    question_id=qid,
                    status=status,
                    last_submitted_at=existing.get("updated_at") or existing.get("created_at"),
                    token=existing.get("judge0_token")
                ))
        return ChallengeTilesResponse(challenge_id=challenge_id, items=items)

question_service = QuestionService()
