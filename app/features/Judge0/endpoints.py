from fastapi import APIRouter, HTTPException, Depends
from typing import List


from app.common.deps import get_current_user, CurrentUser  

from .schemas import (
    CodeSubmissionCreate,
    CodeSubmissionResponse,
    CodeExecutionResult,
    LanguageInfo,
    Judge0Status,
    Judge0SubmissionResponse,
    QuickCodeSubmission,
)
from .service import judge0_service
from app.features.submissions.service import submission_service
from app.features.topic_detections.repository import question_repository
from app.adapters.judge0_client import run_many
from app.features.challenges.repository import challenge_repository
from app.features.topic_detections.service import question_service
from app.features.submissions.schemas import SubmissionCreate
from app.Core.config import get_settings
import asyncpg, ssl, asyncio

# Public router (no authentication required)
public_router = APIRouter(prefix="/judge0", tags=["judge0-public"])

# Protected router (authentication required)
protected_router = APIRouter(prefix="/judge0", tags=["judge0-protected"])

"""Judge0-focused endpoints (execution + token lifecycle).

Submission management (listing, deleting, statistics) moved to `app.features.submissions.endpoints`.
"""

# PUBLIC ENDPOINTS (No authentication required)
@public_router.get("/languages", response_model=List[LanguageInfo])
async def get_supported_languages():
    """Get list of supported programming languages"""
    try:
        return await judge0_service.get_languages()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch languages: {str(e)}")

@public_router.get("/statuses", response_model=List[Judge0Status])
async def get_submission_statuses():
    """Get list of possible submission statuses"""
    try:
        return await judge0_service.get_statuses()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch statuses: {str(e)}")

@public_router.get("/test")
async def test_judge0_connection():
    """Lightweight connectivity test against configured Judge0 URL."""
    try:
        langs = await judge0_service.get_languages()
        return {"status": "connected", "count": len(langs)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Connectivity failed: {str(e)}")

@public_router.post("/submit", response_model=Judge0SubmissionResponse)
async def submit_code(submission: CodeSubmissionCreate):
    """Submit code for async execution (returns token)."""
    try:
        return await judge0_service.submit_code(submission)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit code: {str(e)}")

@public_router.post("/submit/wait", response_model=CodeExecutionResult, summary="Single-call waited execution (no persistence)")
async def submit_code_wait(submission: CodeSubmissionCreate):
    """Submit code with wait=true and return normalized result (no persistence)."""
    try:
        waited = await judge0_service.submit_code_wait(submission)
        return judge0_service._to_code_execution_result(waited, submission.expected_output, submission.language_id)  # type: ignore
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed waited submit: {str(e)}")

@public_router.post("/execute", response_model=CodeExecutionResult)
async def execute_code_sync(submission: CodeSubmissionCreate):
    """Execute and return a normalized result (no persistence).

    Uses Judge0 wait=true internally to avoid returning plain stdout strings.
    """
    try:
        # Single-call wait then normalize to CodeExecutionResult
        waited = await judge0_service.submit_code_wait(submission)
        return judge0_service._to_code_execution_result(waited, submission.expected_output, submission.language_id)  # type: ignore
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Execution timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute code: {str(e)}")

@public_router.post("/execute/stdout", summary="Quick execute (stdout only)")
async def execute_stdout_only(submission: QuickCodeSubmission):
    """Execute code (not persisted) and return only stdout."""
    try:
        result = await judge0_service.execute_quick_code(submission)  # type: ignore
        return {"stdout": result.stdout}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute: {str(e)}")

@public_router.post("/execute/batch", summary="Execute multiple submissions via batch API")
async def execute_batch(submissions: List[CodeSubmissionCreate]):
    """Submit a batch and poll until all complete; returns list of {token, result}."""
    try:
        batch = await judge0_service.execute_batch(submissions)  # type: ignore
        return [{"token": tok, "result": res} for tok, res in batch]
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Batch execution timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed batch execution: {str(e)}")


@public_router.post("/run", summary="Simple run; returns stdout only")
async def run_stdout_only(submission: QuickCodeSubmission):
    try:
        result = await judge0_service.execute_quick_code(submission)  # type: ignore
        return {"stdout": result.stdout, "status_id": result.status_id, "time": result.execution_time, "memory": result.memory_used}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run: {str(e)}")


class _RunTestsBody:
    def __init__(self, source_code: str, language_id: int | None = None):
        self.source_code = source_code
        self.language_id = language_id


@public_router.post("/questions/{question_id}/run-tests", summary="Run code against a question's test cases")
async def run_question_tests(question_id: str, body: dict):
    try:
        src = body.get("source_code")
        lang_override = body.get("language_id")
        if not isinstance(src, str) or not src:
            raise HTTPException(status_code=400, detail="source_code required")
        qmeta = await question_repository.get_question(question_id)
        if not qmeta:
            raise HTTPException(status_code=404, detail="Question not found")
        language_id = int(lang_override) if lang_override is not None else int(qmeta.get("language_id") or 0)
        if not language_id:
            raise HTTPException(status_code=400, detail="language_id missing and not derivable from question")
        tests = await question_repository.list_tests(question_id)
        if not tests:
            raise HTTPException(status_code=404, detail="No tests configured for question")
        items = [
            {"language_id": language_id, "source": src, "stdin": t.get("input"), "expected": t.get("expected")}
            for t in tests
        ]
        results = await run_many(items)
        passed = sum(1 for r in results if r.get("success"))
        failed = len(results) - passed
        detailed = []
        for t, r in zip(tests, results):
            detailed.append({
                "input": t.get("input"),
                "expected": t.get("expected"),
                "visibility": t.get("visibility", "public"),
                "stdout": r.get("stdout"),
                "status_id": r.get("status_id"),
                "status_description": r.get("status_description"),
                "success": r.get("success"),
                "time": r.get("time"),
                "memory": r.get("memory"),
                "token": r.get("token"),
            })
        return {"total": len(results), "passed": passed, "failed": failed, "results": detailed}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run tests: {str(e)}")

# -----------------------------
# Submit then poll Supabase for result (sync service must be running on EC2)
# -----------------------------
_pg_pool: asyncpg.Pool | None = None


async def _get_pg_pool() -> asyncpg.Pool:
    global _pg_pool
    if _pg_pool is not None:
        return _pg_pool
    settings = get_settings()
    dsn = settings.supabase_db_url or settings.database_url
    if not dsn:
        raise HTTPException(status_code=500, detail="SUPABASE_DB_URL not configured")
    ctx = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    _pg_pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4, ssl=ctx, statement_cache_size=0)
    return _pg_pool


async def _poll_supabase_for_token(token: str, max_retries: int = 30, interval_s: float = 1.0):
    pool = await _get_pg_pool()
    for _ in range(max_retries):
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM submissions WHERE token = $1", token)
        if row and (row.get("status_id") or 0) > 2:
            return dict(row)
        await asyncio.sleep(interval_s)
    raise HTTPException(status_code=408, detail="Submission processing timed out")


@public_router.post("/submit/poll", summary="Submit to Judge0 then poll Supabase for result")
async def submit_then_poll(submission: CodeSubmissionCreate):
    try:
        # send to Judge0 (no wait)
        resp = await judge0_service.submit_code(submission)
        # poll Supabase for synced row by token
        result_row = await _poll_supabase_for_token(resp.token)
        return {"token": resp.token, "result": result_row}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"submit_then_poll failed: {str(e)}")

# PROTECTED ENDPOINTS (Authentication required)
@protected_router.post("/submit/full", response_model=Judge0SubmissionResponse, summary="(Auth) Submit and return token (no DB write)")
async def submit_code_full(submission: CodeSubmissionCreate, current_user: CurrentUser = Depends(get_current_user)):
    """Auth submit that returns a Judge0 token without writing to Supabase.

    Storage of raw submission/result is handled by the EC2 sync service; question attempts
    are handled by challenge endpoints.
    """
    try:
        judge0_resp = await judge0_service.submit_code(submission)
        return judge0_resp
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit code (full): {str(e)}")

@protected_router.get("/result/{token}", response_model=CodeExecutionResult)
async def get_execution_result(token: str, current_user: CurrentUser = Depends(get_current_user)):
    """Get execution result by token directly from Judge0 (no DB write).

    Question attempts are managed by challenge endpoints that already store token + result.
    """
    try:
        judge0_result = await judge0_service.get_submission_result(token)
        # If language is present in payload, use it; else -1
        language_id = (judge0_result.language or {}).get("id", -1)
        # When expected_output is unknown here, success falls back to Accepted status check
        success = judge0_service._compute_success(judge0_result.status.get("id"), judge0_result.stdout, None)  # type: ignore
        return CodeExecutionResult(
            stdout=judge0_result.stdout,
            stderr=judge0_result.stderr,
            compile_output=judge0_result.compile_output,
            execution_time=judge0_result.time,
            memory_used=judge0_result.memory,
            status_id=judge0_result.status.get("id", -1),
            status_description=judge0_result.status.get("description", "unknown"),
            language_id=language_id,
            success=success
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error_code":"E_UNKNOWN","message":f"Failed to get result: {str(e)}"})

# For backward compatibility
router = public_router  # Default export is the public router

# NOTE: Submission management endpoints moved to `submissions/endpoints.py`.
