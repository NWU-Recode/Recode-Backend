from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from uuid import UUID

# Use authenticated user instead of passing user_id in query for certain actions
try:  # keep consistent with existing lowercase import usage elsewhere
    from app.auth.service import get_current_user
except ImportError:  # fallback to actual folder case (Windows insensitive, Linux sensitive)
    from app.Auth.service import get_current_user  # type: ignore

from .schemas import (
    CodeSubmissionCreate,
    CodeSubmissionResponse,
    CodeExecutionResult,
    LanguageInfo,
    Judge0Status,
    Judge0SubmissionResponse
)
from .service import judge0_service
from .repository import judge0_repository

router = APIRouter(prefix="/judge0", tags=["judge0"])

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
async def submit_code(submission: CodeSubmissionCreate, user_id: Optional[str] = None):
    """Submit code for execution (async - returns token)"""
    try:
        return await judge0_service.submit_code(submission, user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit code: {str(e)}")

@router.post("/submit/full", response_model=CodeSubmissionResponse, summary="Submit code (auth) and return stored record")
async def submit_code_full(
    submission: CodeSubmissionCreate,
    current_user = Depends(get_current_user)
):
    """Authenticated submit that stores and returns full submission (no user_id query param).

    Uses bearer token to resolve the user, avoiding manual UUID passing & FK errors.
    """
    try:
        user_id = str(current_user.id)
        judge0_resp = await judge0_service.submit_code(submission, user_id)
        db_submission = judge0_repository.get_submission_by_token_sql(judge0_resp.token)
        if not db_submission:
            raise HTTPException(status_code=500, detail="Submission stored record not found after creation")
        return CodeSubmissionResponse(
            id=db_submission.id,
            user_id=db_submission.user_id,
            source_code=db_submission.source_code,
            language_id=db_submission.language_id,
            stdin=db_submission.stdin,
            expected_output=db_submission.expected_output,
            judge0_token=db_submission.judge0_token,
            status=db_submission.status,
            created_at=db_submission.created_at,
            completed_at=db_submission.completed_at
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit code (full): {str(e)}")

@router.get("/result/{token}", response_model=CodeExecutionResult)
async def get_execution_result(token: str):
    """Get execution result by token."""
    try:
        judge0_result = await judge0_service.get_submission_result(token)
        db_submission = judge0_repository.get_submission_by_token_sql(token)
        expected_output = getattr(db_submission, "expected_output", None) if db_submission else None
        language_id = (judge0_result.language or {}).get("id", db_submission.language_id if db_submission else -1)
        success = judge0_service._compute_success(judge0_result.status.get("id"), judge0_result.stdout, expected_output)  # type: ignore

        execution_result = CodeExecutionResult(
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
        # Persist if we have submission and terminal state (id not in queued/processing)
        if db_submission and judge0_result.status.get("id") not in [1, 2]:
            # Attempt store (ignore errors silently here)
            try:
                await judge0_service._store_result(token, execution_result)  # type: ignore
            except Exception:
                pass
        return execution_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get result: {str(e)}")

@router.post("/execute", response_model=CodeExecutionResult)
async def execute_code_sync(submission: CodeSubmissionCreate, user_id: Optional[str] = None):
    """Submit code and wait for execution result (synchronous)"""
    try:
        return await judge0_service.execute_code_sync(submission, user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute code: {str(e)}")

@router.post("/test", response_model=dict)
async def test_code_execution():
    """Test endpoint with a simple Hello World program"""
    try:
        # Simple Python Hello World test
        test_submission = CodeSubmissionCreate(
            source_code='print("Hello, World!")',
            language_id=71  # Python 3
        )
        
        result = await judge0_service.execute_code_sync(test_submission)
        
        return {
            "message": "Test execution completed",
            "result": result,
            "success": result.success
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test execution failed: {str(e)}")

# Additional endpoints for stored submissions (using repository.py)
@router.get("/submissions/user/{user_id}", response_model=List[dict])
async def get_user_submissions(user_id: str, limit: int = 50):
    """(Admin/legacy) Get all submissions for a specific user by id."""
    try:
        return await judge0_service.get_user_submissions(user_id, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch submissions: {str(e)}")

@router.get("/submissions/me", response_model=List[dict], summary="My submissions")
async def get_my_submissions(limit: int = 50, current_user = Depends(get_current_user)):
    """Get submissions for the authenticated user."""
    try:
        return await judge0_service.get_user_submissions(str(current_user.id), limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch submissions: {str(e)}")

@router.get("/submission/{submission_id}/details", response_model=dict)
async def get_submission_details(submission_id: str):
    """Get submission with all its results"""
    try:
        submission = await judge0_service.get_submission_with_results(submission_id)
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")
        return submission
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch submission details: {str(e)}")

@router.delete("/submission/{submission_id}", summary="Delete my submission")
async def delete_submission(submission_id: str, current_user = Depends(get_current_user)):
    """Delete one of the current user's submissions."""
    try:
        success = await judge0_service.delete_user_submission(submission_id, str(current_user.id))
        if not success:
            raise HTTPException(status_code=404, detail="Submission not found or not owned by you")
        return {"message": "Submission deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete submission: {str(e)}")

@router.get("/statistics/languages", response_model=List[dict])
async def get_language_statistics(user_id: Optional[str] = None):
    """Get statistics about language usage (optionally for a given user id)."""
    try:
        return await judge0_service.get_language_statistics(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch statistics: {str(e)}")

@router.get("/statistics/languages/me", response_model=List[dict], summary="My language statistics")
async def get_my_language_statistics(current_user = Depends(get_current_user)):
    try:
        return await judge0_service.get_language_statistics(str(current_user.id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch statistics: {str(e)}")
