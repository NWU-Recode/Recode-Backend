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
)
from .service import judge0_service
from app.features.submissions.service import submission_service
from app.features.questions.repository import question_repository
from app.features.challenges.repository import challenge_repository
from app.features.questions.service import question_service
from app.features.submissions.schemas import SubmissionCreate


router = APIRouter(prefix="/judge0", tags=["judge0"])

"""Judge0-focused endpoints (execution + token lifecycle).

Submission management (listing, deleting, statistics) moved to `app.features.submissions.endpoints`.
"""
@router.get("/languages", response_model=List[LanguageInfo])
async def get_supported_languages():
    """Get list of supported programming languages"""
    try:
        return await judge0_service.get_languages()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch languages: {str(e)}")

@router.get("/statuses", response_model=List[Judge0Status])
async def get_submission_statuses():
    """Get list of possible submission statuses"""
    try:
        return await judge0_service.get_statuses()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch statuses: {str(e)}")

@router.post("/submit", response_model=Judge0SubmissionResponse)
async def submit_code(submission: CodeSubmissionCreate):
    """Submit code for async execution (returns token)."""
    try:
        return await judge0_service.submit_code(submission)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit code: {str(e)}")

@router.post("/submit/wait", response_model=CodeExecutionResult, summary="Single-call waited execution (no persistence)")
async def submit_code_wait(submission: CodeSubmissionCreate):
    """Submit code with wait=true and return normalized result (no persistence)."""
    try:
        waited = await judge0_service.submit_code_wait(submission)
        return judge0_service._to_code_execution_result(waited, submission.expected_output, submission.language_id)  # type: ignore
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed waited submit: {str(e)}")

@router.post("/submit/full", response_model=CodeSubmissionResponse, summary="(Auth) Submit & persist")
async def submit_code_full(submission: CodeSubmissionCreate, current_user: CurrentUser = Depends(get_current_user)):
    """Submit code (auth), persist a record, return stored submission row + token."""
    try:
        user_id = str(current_user.id)
        judge0_resp = await judge0_service.submit_code(submission)
        # Persist initial submission row
        await submission_service.store_submission(
            submission=submission,  # type: ignore[arg-type]
            user_id=user_id,
            judge0_token=judge0_resp.token
        )
        created = await submission_service.get_submission_by_token(judge0_resp.token)
        if not created:
            raise HTTPException(status_code=500, detail="Submission record not found after creation")
        return CodeSubmissionResponse(**created)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit code (full): {str(e)}")

@router.get("/result/{token}", response_model=CodeExecutionResult)
async def get_execution_result(token: str, current_user: CurrentUser = Depends(get_current_user)):
    """Get execution result by token. Finalizes pending question attempt if applicable."""

    try:
        user_id = str(current_user.id)
        judge0_result = await judge0_service.get_submission_result(token)
        db_submission = await submission_service.get_submission_by_token(token)
        expected_output = db_submission.get("expected_output") if db_submission else None
        language_id = (judge0_result.language or {}).get("id", db_submission.get("language_id") if db_submission else -1)
        success = judge0_service._compute_success(judge0_result.status.get("id"), judge0_result.stdout, expected_output)  # type: ignore
        exec_result = CodeExecutionResult(
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
        status_id = judge0_result.status.get("id") if judge0_result.status else None
        if db_submission and status_id not in [1, 2]:
            # Persist result row (ignore errors)
            try:
                await submission_service.store_result(token, exec_result)
            except Exception:
                pass
            # If this corresponds to a question & no question_attempt yet, create one
            qid = db_submission.get("question_id")
            if qid:
                existing_attempt = await question_repository.find_by_token(qid, user_id, token)
                if not existing_attempt:
                    # Need challenge_id from question
                    qmeta = await question_repository.get_question(qid)
                    if qmeta:
                        attempt = await challenge_repository.create_or_get_open_attempt(str(qmeta["challenge_id"]), user_id)
                        # Build attempt payload
                        payload = {
                            "question_id": qid,
                            "challenge_id": str(qmeta["challenge_id"]),
                            "challenge_attempt_id": attempt["id"],
                            "user_id": user_id,
                            "judge0_token": token,
                            "source_code": db_submission.get("source_code"),
                            "stdout": exec_result.stdout,
                            "stderr": exec_result.stderr,
                            "status_id": exec_result.status_id,
                            "status_description": exec_result.status_description,
                            "time": exec_result.execution_time,
                            "memory": exec_result.memory_used,
                            "is_correct": success,
                            "code_hash": None,
                            "hash": None,
                            "latest": True,
                        }
                        existing_latest = await question_repository.get_existing_attempt(qid, user_id)
                        if existing_latest:
                            await question_repository.mark_previous_not_latest(qid, user_id)
                        await question_repository.upsert_attempt(payload)
        return exec_result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error_code":"E_UNKNOWN","message":f"Failed to get result: {str(e)}"})

@router.post("/execute", response_model=CodeExecutionResult)
async def execute_code_sync(submission: CodeSubmissionCreate):
    """Legacy execute endpoint (polling). Prefer /submit/wait if immediate result acceptable."""
    try:
        return await judge0_service.execute_code(submission)
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Execution timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute code: {str(e)}")

@router.post("/execute/stdout", summary="Quick execute (stdout only)")
async def execute_stdout_only(submission: CodeSubmissionCreate):
    """Execute code (no expected_output, not persisted) and return only stdout."""
    try:
        temp = CodeSubmissionCreate(
            source_code=submission.source_code,
            language_id=submission.language_id,
            stdin=submission.stdin,
            expected_output=None  # ignore any provided expected output
        )
        result = await judge0_service.execute_code(temp)  # type: ignore
        return {"stdout": result.stdout}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute: {str(e)}")

@router.post("/execute/batch", summary="Execute multiple submissions via batch API")
async def execute_batch(submissions: List[CodeSubmissionCreate]):
    """Submit a batch and poll until all complete; returns list of {token, result}."""
    try:
        batch = await judge0_service.execute_batch(submissions)  # type: ignore
        return [{"token": tok, "result": res} for tok, res in batch]
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Batch execution timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed batch execution: {str(e)}")


@router.post("/test", response_model=dict)
async def test_code_execution():
    """Test endpoint with a simple Hello World program"""
    try:
        # Simple Python Hello World test
        test_submission = CodeSubmissionCreate(
            source_code='print("Hello, World!")',
            language_id=71  # Python 3
        )
        result = await judge0_service.execute_code(test_submission)  # type: ignore
        return {
            "message": "Test execution completed",
            "result": result,
            "success": result.success
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test execution failed: {str(e)}")

# NOTE: Submission management endpoints moved to `submissions/endpoints.py`.
