from __future__ import annotations
from typing import Optional, Dict, Any
from .repository import question_repository
from .schemas import (
    ExecuteRequest, ExecuteResponse,
    QuestionSubmitRequest, QuestionSubmitResponse,
    BatchExecuteRequest, BatchExecuteResponse, BatchExecuteItemResponse,
    BatchSubmitRequest, BatchSubmitResponse, BatchSubmitItemResponse
)
import hashlib
from fastapi import HTTPException
from app.features.judge0.schemas import CodeSubmissionCreate
from app.features.judge0.service import judge0_service
from app.features.challenges.repository import challenge_repository
from app.DB.client import get_supabase

class QuestionService:
    async def execute(self, req: ExecuteRequest, user_id: str) -> ExecuteResponse:
        q = await question_repository.get_question(str(req.question_id))
        if not q:
            raise ValueError("Question not found")
        # Hash includes expected_output for staleness safety
        hasher = hashlib.sha256()
        composite = f"{q['language_id']}\n{req.stdin or ''}\n{req.source_code}\n{q.get('expected_output') or ''}".encode()
        hasher.update(composite)
        code_hash = hasher.hexdigest()
        # Cache reuse: if an existing attempt with same code_hash graded, reuse its stdout
        cached = await question_repository.find_by_code_hash(str(req.question_id), user_id, code_hash)
        if cached and cached.get("is_correct") is not None:
            return ExecuteResponse(
                judge0_token=cached.get("judge0_token", ""),
                stdout=cached.get("stdout"),
                stderr=cached.get("stderr"),
                status_id=cached.get("status_id", -1),
                status_description=cached.get("status_description", "cached"),
                is_correct=None,  # preview stays neutral
                time=cached.get("time"),
                memory=cached.get("memory"),
            )
        submission = CodeSubmissionCreate(
            source_code=req.source_code,
            language_id=q["language_id"],
            stdin=req.stdin,
            expected_output=None  # execute preview does not grade
        )
        # Per spec: use execute_with_token (polling) rather than waited submit for execute path
        token, result = await judge0_service.execute_with_token(submission)  # type: ignore
        is_correct = None  # preview does not grade
        return ExecuteResponse(
            judge0_token=token,
            stdout=result.stdout,
            stderr=result.stderr,
            status_id=result.status_id,
            status_description=result.status_description,
            is_correct=is_correct,
            time=result.execution_time,
            memory=result.memory_used,
        )

    async def submit(self, req: QuestionSubmitRequest, user_id: str) -> QuestionSubmitResponse:
        q = await question_repository.get_question(str(req.question_id))
        if not q:
            raise ValueError("Question not found")
        # Ensure open challenge attempt exists for user/challenge
        challenge_id = str(q["challenge_id"])
        attempt = await challenge_repository.get_open_attempt(challenge_id, user_id)
        if not attempt:
            attempt = await challenge_repository.start_attempt(challenge_id, user_id)
        hasher = hashlib.sha256()
        composite = f"{q['language_id']}\n{req.stdin or ''}\n{req.source_code}\n{q.get('expected_output') or ''}".encode()
        hasher.update(composite)
        code_hash = hasher.hexdigest()
        idempotency_key = req.idempotency_key
        # Idempotent replay: if key supplied and existing attempt with that key exists, return it immediately
        if idempotency_key:
            existing_idem = await question_repository.find_by_idempotency_key(str(req.question_id), user_id, idempotency_key)
            if existing_idem:
                points_awarded = existing_idem.get("points_awarded") or (q.get("points") if existing_idem.get("is_correct") else 0)
                return QuestionSubmitResponse(
                    question_attempt_id=existing_idem["id"],
                    judge0_token=existing_idem.get("judge0_token", ""),
                    is_correct=existing_idem.get("is_correct", False),
                    stdout=existing_idem.get("stdout"),
                    stderr=existing_idem.get("stderr"),
                    status_id=existing_idem.get("status_id", -1),
                    status_description=existing_idem.get("status_description", "idempotent-replay"),
                    time=existing_idem.get("time"),
                    memory=existing_idem.get("memory"),
                    points_awarded=points_awarded or 0,
                )
        # Cache shortcut: same code_hash and previous attempt graded correct or incorrect -> reuse
        cached = await question_repository.find_by_code_hash(str(req.question_id), user_id, code_hash)
        if cached and cached.get("is_correct") is not None:
            points_awarded = cached.get("points_awarded") or (q.get("points") if cached.get("is_correct") else 0)
            return QuestionSubmitResponse(
                question_attempt_id=cached["id"],
                judge0_token=cached.get("judge0_token", ""),
                is_correct=cached.get("is_correct", False),
                stdout=cached.get("stdout"),
                stderr=cached.get("stderr"),
                status_id=cached.get("status_id", -1),
                status_description=cached.get("status_description", "cached"),
                time=cached.get("time"),
                memory=cached.get("memory"),
                points_awarded=points_awarded or 0,
            )
        submission = CodeSubmissionCreate(
            source_code=req.source_code,
            language_id=q["language_id"],
            stdin=req.stdin,
            expected_output=q.get("expected_output")
        )
        # Attach question_id for submission join by temporarily setting on submission object clone
        token, result = await judge0_service.submit_question_run(submission, user_id)
        # Update the code_submissions row with question_id if missing (simple patch update)
        try:
            from app.features.submissions.repository import submission_repository
            sub_row = await submission_repository.get_by_token(token)  # type: ignore
            if sub_row and not sub_row.get("question_id"):
                client = await get_supabase()  # type: ignore
                client.table("code_submissions").update({"question_id": str(req.question_id)}).eq("id", sub_row["id"]).execute()
        except Exception:
            pass
        is_correct = result.success
        existing = await question_repository.get_existing_attempt(str(req.question_id), user_id)
        payload = {
            "question_id": str(req.question_id),
            "challenge_id": str(q["challenge_id"]),
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
            "idempotency_key": idempotency_key,
            "latest": True,
        }
        if existing:
            await question_repository.mark_previous_not_latest(str(req.question_id), user_id)
            payload["id"] = existing["id"]
        stored = await question_repository.upsert_attempt(payload)
        points_awarded = q.get("points") if is_correct else 0
        return QuestionSubmitResponse(
            question_attempt_id=stored["id"],
            judge0_token=token,
            is_correct=is_correct,
            stdout=result.stdout,
            stderr=result.stderr,
            status_id=result.status_id,
            status_description=result.status_description,
            time=result.execution_time,
            memory=result.memory_used,
            points_awarded=points_awarded or 0,
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
            composite = f"{q['language_id']}\n{stdin_val or ''}\n{src}\n{q.get('expected_output') or ''}".encode()
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
            points_awarded = q.get("points") if is_correct else 0
            responses.append(BatchSubmitItemResponse(
                question_id=question_id,
                question_attempt_id=stored["id"],
                judge0_token=token,
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
            points_awarded = q.get("points") if existing.get("is_correct") else 0
            responses.append(BatchSubmitItemResponse(
                question_id=qid,
                question_attempt_id=existing["id"],
                judge0_token=existing.get("judge0_token", ""),
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

question_service = QuestionService()
