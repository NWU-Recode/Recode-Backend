from __future__ import annotations

import asyncio
import logging
import ssl
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from app.Core.config import get_settings
from app.adapters.judge0_client import run_many
from app.common.deps import CurrentUser, get_current_user
from app.features.challenges.repository import challenge_repository
from app.features.judge0.schemas import (
    CodeExecutionResult,
    CodeSubmissionCreate,
    CodeSubmissionResponse,
    Judge0ExecutionResult,
    Judge0Status,
    Judge0SubmissionResponse,
    Judge0SubmissionResponseWithMeta,
    LanguageInfo,
    QuickCodeSubmission,
)
from app.features.judge0.service import judge0_service
from app.features.submissions.code_results_repository import code_results_repository

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

public_router = APIRouter(prefix="/judge0", tags=["judge0-public"])
protected_router = APIRouter(prefix="/judge0", tags=["judge0-protected"])


# ---------------------------------------------------------------------------
# Utility helpers (Supabase polling for submit/poll)
# ---------------------------------------------------------------------------
_pg_pool = None  # lazy initialised asyncpg pool


async def _get_pg_pool():
    """Create (or reuse) an asyncpg pool targeting the configured Supabase database."""
    global _pg_pool
    if _pg_pool is not None:
        return _pg_pool

    settings = get_settings()
    dsn = settings.supabase_db_url or settings.database_url
    if not dsn:
        raise HTTPException(status_code=500, detail="SUPABASE_DB_URL not configured")

    try:
        import asyncpg  # type: ignore
    except ImportError as exc:  # pragma: no cover - ensured in deployment
        raise HTTPException(status_code=500, detail="asyncpg not installed. Run: pip install asyncpg") from exc

    ctx = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED

    _pg_pool = await asyncpg.create_pool(
        dsn,
        min_size=1,
        max_size=4,
        ssl=ctx,
        statement_cache_size=0,
    )
    return _pg_pool


async def _poll_supabase_for_token(token: str, max_retries: int = 30, interval_s: float = 1.0) -> Dict[str, Any]:
    """Poll Supabase `code_submissions` for a row matching the Judge0 token."""
    pool = await _get_pg_pool()
    for _ in range(max_retries):
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM code_submissions WHERE token = $1", token)
        if row:
            # Ensure the submission has completed; `status_id` > 2 typically means finished in Judge0
            status_id = row.get("status_id") if isinstance(row, dict) else row["status_id"]
            if status_id is None or status_id > 2:
                return dict(row)
        await asyncio.sleep(interval_s)
    raise HTTPException(status_code=408, detail="Submission processing timed out")


def _to_poll_payload(result: Judge0ExecutionResult) -> Dict[str, Any]:
    status = result.status or {}
    return {
        "token": result.token,
        "status_id": status.get("id"),
        "status_description": status.get("description"),
        "stdout": result.stdout,
        "stderr": result.stderr,
        "time": result.time,
        "wall_time": result.time,
        "memory": result.memory,
        "language": result.language,
    }


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------

@public_router.get("/languages", response_model=List[LanguageInfo])
async def get_supported_languages():
    try:
        return await judge0_service.get_languages()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch languages: {exc}") from exc


@public_router.get("/statuses", response_model=List[Judge0Status])
async def get_submission_statuses():
    try:
        return await judge0_service.get_statuses()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch statuses: {exc}") from exc


@public_router.get("/test")
async def test_judge0_connection():
    try:
        langs = await judge0_service.get_languages()
        return {"status": "connected", "count": len(langs)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Connectivity failed: {exc}") from exc


@public_router.post("/submit", response_model=Judge0SubmissionResponse)
async def submit_code(submission: CodeSubmissionCreate):
    try:
        return await judge0_service.submit_code(submission)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to submit code: {exc}") from exc


@public_router.post("/submit/wait", response_model=CodeExecutionResult, summary="Single-call waited execution (no persistence)")
async def submit_code_wait(submission: CodeSubmissionCreate):
    try:
        waited = await judge0_service.submit_code_wait(submission)
        return judge0_service._to_code_execution_result(waited, submission.expected_output, submission.language_id)  # type: ignore
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed waited submit: {exc}") from exc


@public_router.post("/submit/poll", summary="Submit to Judge0 then poll Supabase for result")
async def submit_then_poll(submission: CodeSubmissionCreate):
    try:
        response = await judge0_service.submit_code(submission)
        try:
            result_row = await _poll_supabase_for_token(response.token)
            return {"token": response.token, "result": result_row}
        except Exception as poll_exc:
            # If Supabase/Postgres polling fails, fall back to synchronously fetching Judge0 result
            logger = logging.getLogger(__name__)
            logger.warning("Supabase polling failed (%s). Falling back to direct Judge0 polling.", poll_exc)
            token = response.token
            start = time.time()
            timeout_seconds = 60
            poll_interval = 1.0
            while time.time() - start < timeout_seconds:
                try:
                    judge0_result = await judge0_service.get_submission_result(token)
                except Exception as fetch_exc:
                    logger.debug("Failed to fetch Judge0 submission result: %s", fetch_exc)
                    await asyncio.sleep(poll_interval)
                    continue
                status_id = judge0_result.status.get("id") if judge0_result.status else None
                if status_id not in (1, 2):
                    out = _to_poll_payload(judge0_result)
                    try:
                        submission_id = await code_results_repository.create_submission(
                            user_id=0,
                            language_id=judge0_result.language.get("id") if judge0_result.language else -1,
                            source_code=submission.source_code,
                            token=token,
                            stdin=submission.stdin,
                            expected_output=submission.expected_output,
                            summary={
                                "status_id": out.get("status_id"),
                                "stdout": out.get("stdout"),
                                "stderr": out.get("stderr"),
                                "time": out.get("time"),
                                "wall_time": out.get("wall_time"),
                                "memory": out.get("memory"),
                                "message": out.get("status_description"),
                                "finished_at": datetime.utcnow(),
                            },
                        )
                        if submission_id:
                            await code_results_repository.insert_results(
                                submission_id,
                                [
                                    {
                                        "stdout": judge0_result.stdout,
                                        "stderr": judge0_result.stderr,
                                        "compile_output": judge0_result.compile_output,
                                        "execution_time": judge0_result.time,
                                        "memory_used": judge0_result.memory,
                                        "status_id": out.get("status_id"),
                                        "status_description": out.get("status_description", "unknown"),
                                        "token": token,
                                    }
                                ],
                            )
                    except Exception:
                        logger.exception("Failed to persist Judge0 submission fallback result")
                    return {"token": token, "result": out}
                await asyncio.sleep(poll_interval)
            raise HTTPException(status_code=408, detail="Submission processing timed out (fallback polling)")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"submit_then_poll failed: {exc}") from exc


@public_router.post("/execute", response_model=CodeExecutionResult)
async def execute_code_sync(submission: CodeSubmissionCreate):
    try:
        waited = await judge0_service.submit_code_wait(submission)
        return judge0_service._to_code_execution_result(waited, submission.expected_output, submission.language_id)  # type: ignore
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Execution timeout")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to execute code: {exc}") from exc


@public_router.post("/execute/stdout", summary="Quick execute (stdout only)")
async def execute_stdout_only(submission: QuickCodeSubmission):
    try:
        result = await judge0_service.execute_quick_code(submission)  # type: ignore
        return {"stdout": result.stdout}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to execute: {exc}") from exc


@public_router.post("/execute/simple", summary="Execute with expected; returns stdout + success")
async def execute_simple(submission: CodeSubmissionCreate):
    try:
        waited = await judge0_service.submit_code_wait(submission)
        status_id = waited.status.get("id") if waited.status else None
        success = judge0_service._compute_success(status_id, waited.stdout, submission.expected_output)  # type: ignore
        return {"stdout": waited.stdout or "", "success": bool(success)}
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Execution timeout")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to execute code: {exc}") from exc


@public_router.post("/execute/batch", summary="Execute multiple submissions via batch API")
async def execute_batch(submissions: List[CodeSubmissionCreate], timeout_s: Optional[int] = 180):
    try:
        batch = await judge0_service.execute_batch(submissions, timeout_seconds=timeout_s)  # type: ignore
        return [{"token": tok, "result": res} for tok, res in batch]
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Batch execution timed out")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to execute batch: {exc}") from exc


# ---------------------------------------------------------------------------
# Protected endpoints (auth required)
# ---------------------------------------------------------------------------

@protected_router.post("/submit/full", response_model=Judge0SubmissionResponseWithMeta, summary="(Auth) Submit and return token (no DB write)")
async def submit_code_full(submission: CodeSubmissionCreate, current_user: CurrentUser = Depends(get_current_user)):
    try:
        judge0_resp = await judge0_service.submit_code(submission)
        token = judge0_resp.token
        try:
            import hashlib

            submission_id: Optional[int] = int(hashlib.sha256(token.encode()).hexdigest()[:8], 16)
        except Exception:
            submission_id = None
        created_at = datetime.utcnow()
        return Judge0SubmissionResponseWithMeta(token=token, submission_id=submission_id, created_at=created_at)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to submit code (full): {exc}") from exc


@protected_router.get("/result/{token}", response_model=CodeExecutionResult)
async def get_execution_result(token: str, current_user: CurrentUser = Depends(get_current_user)):
    try:
        judge0_result = await judge0_service.get_submission_result(token)
        exec_result = judge0_service._to_code_execution_result(judge0_result, None, None)
        return exec_result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error_code": "E_UNKNOWN", "message": f"Failed to get result: {exc}"}) from exc


# ---------------------------------------------------------------------------
# Backwards compatibility exports
# ---------------------------------------------------------------------------

router = public_router

