from __future__ import annotations
from typing import Optional, Dict, Any, List
from datetime import datetime

from .schemas import SubmissionCreate, SubmissionResultCreate
from .repository import submission_repository
from app.features.judge0.schemas import CodeExecutionResult

class SubmissionService:
    async def store_submission(self, submission: SubmissionCreate, user_id: str, judge0_token: str) -> Dict[str, Any]:
        return await submission_repository.create_submission(submission, user_id, judge0_token)

    async def store_result(self, judge0_token: str, exec_result: CodeExecutionResult) -> Dict[str, Any]:
        sub = await submission_repository.get_by_token(judge0_token)
        if not sub:
            raise RuntimeError("Submission not found for token")
        payload = SubmissionResultCreate(
            submission_id=sub["id"],
            stdout=exec_result.stdout,
            stderr=exec_result.stderr,
            compile_output=exec_result.compile_output,
            execution_time=exec_result.execution_time,
            memory_used=exec_result.memory_used,
            status_id=exec_result.status_id,
            status_description=exec_result.status_description,
            language_id=exec_result.language_id,
        )
        return await submission_repository.create_result(payload)

    async def get_submission_with_results(self, submission_id: str) -> Optional[Dict[str, Any]]:
        return await submission_repository.get_with_results(submission_id)

    async def get_submission_by_token(self, judge0_token: str) -> Optional[Dict[str, Any]]:
        return await submission_repository.get_by_token(judge0_token)

    async def list_user_submissions(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        return await submission_repository.list_user_submissions(user_id, limit)

    async def delete_submission(self, submission_id: str, user_id: str) -> bool:
        return await submission_repository.delete_submission(submission_id, user_id)

    async def language_statistics(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return await submission_repository.language_statistics(user_id)

submission_service = SubmissionService()
