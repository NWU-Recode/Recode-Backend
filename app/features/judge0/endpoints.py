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

router = APIRouter(prefix="/judge0", tags=["judge0-public"])


@router.get("/languages", response_model=List[LanguageInfo])
async def get_supported_languages():
    """Return the Judge0 language catalogue."""
    try:
        return await judge0_service.get_languages()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch languages: {str(e)}")


@router.get("/statuses", response_model=List[Judge0Status])
async def get_submission_statuses():
    """Return available Judge0 submission statuses."""
    try:
        return await judge0_service.get_statuses()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch statuses: {str(e)}")


@router.post("/execute/stdout", summary="Quick execute (stdout only)")
async def execute_stdout_only(submission: QuickCodeSubmission):
    """Execute code without persistence and return stdout only."""
    try:
        result = await judge0_service.execute_quick_code(submission)  # type: ignore
        return {"stdout": result.stdout}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute: {str(e)}")

# Backwards-compatible exports expected by app.main
public_router = router
protected_router = router

