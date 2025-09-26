from fastapi import APIRouter, HTTPException, Depends
from typing import List


from app.common.deps import get_current_user, CurrentUser

from datetime import datetime

from app.features.judge0.schemas import (
    CodeSubmissionCreate,
    CodeSubmissionResponse,
    CodeExecutionResult,
    LanguageInfo,
    Judge0Status,
    Judge0SubmissionResponse,
    QuickCodeSubmission,
    Judge0SubmissionResponseWithMeta,
)
from app.features.judge0.service import judge0_service
from app.adapters.judge0_client import run_many
from app.features.challenges.repository import challenge_repository
from app.Core.config import get_settings
from app.features.submissions.code_results_repository import code_results_repository
import ssl, asyncio, time, logging

public_router = APIRouter(prefix="/judge0", tags=["judge0-public"])
protected_router = APIRouter(prefix="/judge0", tags=["judge0-protected"])

@public_router.get("/languages", response_model=List[LanguageInfo])
async def get_supported_languages():
    """Return the Judge0 language catalogue."""
    try:
        return await judge0_service.get_languages()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch languages: {str(e)}")

@public_router.get("/statuses", response_model=List[Judge0Status])
async def get_submission_statuses():
    """Return available Judge0 submission statuses."""
    try:
        return await judge0_service.get_statuses()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch statuses: {str(e)}")

@public_router.get("/test")
async def test_judge0_connection():
    """Perform a lightweight connectivity test."""
    try:
        langs = await judge0_service.get_languages()
        return {"status": "connected", "count": len(langs)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Connectivity failed: {str(e)}")

@public_router.post("/submit", response_model=Judge0SubmissionResponse)
async def submit_code(submission: CodeSubmissionCreate):
    """Submit code for asynchronous execution."""
    try:
        return await judge0_service.submit_code(submission)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit code: {str(e)}")

@public_router.post("/submit/wait", response_model=CodeExecutionResult, summary="Single-call waited execution (no persistence)")
async def submit_code_wait(submission: CodeSubmissionCreate):
    """Submit code and wait for completion before returning the result."""
    try:
        waited = await judge0_service.submit_code_wait(submission)
        return judge0_service._to_code_execution_result(waited, submission.expected_output, submission.language_id)  # type: ignore
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed waited submit: {str(e)}")

@public_router.post("/execute", response_model=CodeExecutionResult)
async def execute_code_sync(submission: CodeSubmissionCreate):
    """Execute code and return a normalized result without persistence."""
    try:
        waited = await judge0_service.submit_code_wait(submission)
        return judge0_service._to_code_execution_result(waited, submission.expected_output, submission.language_id)  # type: ignore
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Execution timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute code: {str(e)}")

@public_router.post("/execute/stdout", summary="Quick execute (stdout only)")
async def execute_stdout_only(submission: QuickCodeSubmission):
    """Execute code without persistence and return stdout only."""
    try:
        result = await judge0_service.execute_quick_code(submission)  # type: ignore
        return {"stdout": result.stdout}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute: {str(e)}")

@public_router.post("/execute/simple", summary="Execute with expected; returns stdout + success")
async def execute_simple(submission: CodeSubmissionCreate):
    try:
        waited = await judge0_service.submit_code_wait(submission)
        status_id = waited.status.get("id") if waited.status else None
        success = judge0_service._compute_success(status_id, waited.stdout, submission.expected_output)  # type: ignore
        return {"stdout": waited.stdout or "", "success": bool(success)}
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Execution timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute code: {str(e)}")

@public_router.post("/execute/batch", summary="Execute multiple submissions via batch API")
async def execute_batch(submissions: List[CodeSubmissionCreate], timeout_s: int | None = 180):
    """Execute a batch and return a token-result mapping."""
    try:
        batch = await judge0_service.execute_batch(submissions, timeout_seconds=timeout_s)  # type: ignore
        return [{"token": tok, "result": res} for tok, res in batch]
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Batch execution timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed batch execution: {str(e)}")


@public_router.post("/run", summary="Simple run; returns stdout only")
async def run_stdout_only(submission: QuickCodeSubmission):
    try:
        result = await judge0_service.execute_quick_code(submission)  # type: ignore
        return {"stdout": result.stdout}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run: {str(e)}")


class _RunTestsBody:
    def __init__(self, source_code: str, language_id: int | None = None):
        self.source_code = source_code
        self.language_id = language_id


_pg_pool = None


async def _get_pg_pool():
    global _pg_pool
    if _pg_pool is not None:
        return _pg_pool
    settings = get_settings()
    dsn = settings.supabase_db_url or settings.database_url
    if not dsn:
        raise HTTPException(status_code=500, detail="SUPABASE_DB_URL not configured")
    try:
        import asyncpg  # type: ignore
    except ImportError:
        raise HTTPException(status_code=500, detail="asyncpg not installed. Run: pip install asyncpg")
    ctx = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    _pg_pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4, ssl=ctx, statement_cache_size=0)
    return _pg_pool


async def _poll_supabase_for_token(token: str, max_retries: int = 30, interval_s: float = 1.0):
    pool = await _get_pg_pool()
    for _ in range(max_retries):
        async with pool.acquire() as conn:
            # The project migrated to using code_submissions with token column
            row = await conn.fetchrow("SELECT * FROM code_submissions WHERE token = $1", token)
        if row and (row.get("status_id") or 0) > 2:
            return dict(row)
        await asyncio.sleep(interval_s)
    raise HTTPException(status_code=408, detail="Submission processing timed out")


@public_router.post("/submit/poll", summary="Submit to Judge0 then poll Supabase for result")
async def submit_then_poll(submission: CodeSubmissionCreate):
    try:
        resp = await judge0_service.submit_code(submission)
        try:
            result_row = await _poll_supabase_for_token(resp.token)
            return {"token": resp.token, "result": result_row}
        except Exception as db_exc:
            # If Supabase/Postgres is unreachable (DNS/getaddrinfo or connection errors),
            # fall back to polling Judge0 directly so the endpoint remains functional.
            logger = logging.getLogger(__name__)
            logger.warning("Supabase polling failed (%s). Falling back to direct Judge0 polling.", str(db_exc))
            # Poll Judge0 directly for the submission result with a reasonable timeout
            token = resp.token
            start = time.time()
            timeout_seconds = 60
            poll_interval = 1.0
            while time.time() - start < timeout_seconds:
                try:
                    judge0_result = await judge0_service.get_submission_result(token)
                except Exception as e:
                    # If Judge0 itself is temporarily unreachable, wait and retry
                    logger.debug("Failed to fetch Judge0 submission result: %s", str(e))
                    await asyncio.sleep(poll_interval)
                    continue
                status_id = judge0_result.status.get("id") if judge0_result.status else None
                if status_id not in [1, 2]:
                    # Convert Judge0ExecutionResult into a plain dict similar enough to DB row
                    out = {
                        "token": token,
                        "status_id": status_id,
                        "status_description": (judge0_result.status or {}).get("description", "unknown"),
                        "stdout": judge0_result.stdout,
                        "stderr": judge0_result.stderr,
                        "time": judge0_result.time,
                        "memory": judge0_result.memory,
                        "language": judge0_result.language,
                    }
                    # Persist submission and result into code_submissions/code_results so later components can use them
                    try:
                        # create a submission row; user_id is unknown for public endpoint so use 0
                        sub_id = await code_results_repository.create_submission(
                            user_id=0,
                            language_id=judge0_result.language.get("id") if judge0_result.language else -1,
                            source_code=submission.source_code,
                            token=token,
                        )
                        if sub_id:
                            await code_results_repository.insert_results(sub_id, [out])
                    except Exception:
                        # Don't block the response if DB write fails; log and continue
                        logging.getLogger(__name__).exception("Failed to persist Judge0 submission/result")
                    return {"token": token, "result": out}
                await asyncio.sleep(poll_interval)
            raise HTTPException(status_code=408, detail="Submission processing timed out (fallback polling)")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"submit_then_poll failed: {str(e)}")

@protected_router.post("/submit/full", response_model=Judge0SubmissionResponseWithMeta, summary="(Auth) Submit and return token (no DB write)")
async def submit_code_full(submission: CodeSubmissionCreate, current_user: CurrentUser = Depends(get_current_user)):
    """Submit code with authentication but without persisting the payload."""
    try:
        judge0_resp = await judge0_service.submit_code(submission)
        # Provide a deterministic submission_id and created_at where possible
        # Use the same derivation as in _to_code_execution_result
        token = judge0_resp.token
        # compute stable small int from token
        try:
            import hashlib
            submission_id = int(hashlib.sha256(token.encode()).hexdigest()[:8], 16)
        except Exception:
            submission_id = None
        created_at = datetime.utcnow()
        return Judge0SubmissionResponseWithMeta(token=token, submission_id=submission_id, created_at=created_at)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit code (full): {str(e)}")

@protected_router.get("/result/{token}", response_model=CodeExecutionResult)
async def get_execution_result(token: str, current_user: CurrentUser = Depends(get_current_user)):
    """Fetch an execution result directly from Judge0 without persistence."""
    try:
        judge0_result = await judge0_service.get_submission_result(token)
        # Use the service helper to produce a CodeExecutionResult with submission_id/created_at
        exec_result = judge0_service._to_code_execution_result(judge0_result, None, None)
        return exec_result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error_code":"E_UNKNOWN","message":f"Failed to get result: {str(e)}"})

# For backward compatibility
router = public_router

