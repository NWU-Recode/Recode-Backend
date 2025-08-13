from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from uuid import UUID

from .schemas import (
    CodeSubmissionCreate,
    CodeSubmissionResponse,
    CodeExecutionResult,
    LanguageInfo,
    Judge0Status,
    Judge0SubmissionResponse
)
from .service import judge0_service

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

@router.get("/result/{token}", response_model=CodeExecutionResult)
async def get_execution_result(token: str):
    """Get execution result by token"""
    try:
        judge0_result = await judge0_service.get_submission_result(token)
        
        # Convert to our format
        return CodeExecutionResult(
            stdout=judge0_result.stdout,
            stderr=judge0_result.stderr,
            compile_output=judge0_result.compile_output,
            execution_time=judge0_result.time,
            memory_used=judge0_result.memory,
            status_id=judge0_result.status.get("id", -1),
            status_description=judge0_result.status.get("description", "unknown"),
            language_id=(judge0_result.language or {}).get("id", -1),
            success=judge0_result.status.get("id") == 3  # 3=Accepted
        )
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
    """Get all submissions for a user"""
    try:
        return await judge0_service.get_user_submissions(user_id, limit)
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

@router.delete("/submission/{submission_id}")
async def delete_submission(submission_id: str, user_id: str):
    """Delete a submission (only if it belongs to the user)"""
    try:
        success = await judge0_service.delete_user_submission(submission_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Submission not found or you don't have permission to delete it")
        return {"message": "Submission deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete submission: {str(e)}")

@router.get("/statistics/languages", response_model=List[dict])
async def get_language_statistics(user_id: Optional[str] = None):
    """Get statistics about language usage"""
    try:
        return await judge0_service.get_language_statistics(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch statistics: {str(e)}")
