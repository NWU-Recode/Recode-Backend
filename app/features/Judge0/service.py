import httpx
import asyncio
import time
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import uuid4

from app.core.config import get_settings
from .repository import judge0_repository
from .schemas import (
    CodeSubmissionCreate,
    CodeSubmissionResponse,
    Judge0SubmissionRequest,
    Judge0SubmissionResponse,
    Judge0ExecutionResult,
    CodeExecutionResult,
    LanguageInfo,
    Judge0Status
)

class Judge0Service:
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.judge0_api_url
        # Build headers conditionally (RapidAPI vs direct instance)
        self.headers = {"Content-Type": "application/json"}
        if self.settings.judge0_api_key and self.settings.judge0_host:
            self.headers.update({
                "X-RapidAPI-Key": self.settings.judge0_api_key,
                "X-RapidAPI-Host": self.settings.judge0_host,
            })

    @staticmethod
    def _compute_success(status_id: int | None, stdout: str | None, expected_output: str | None) -> bool:
        """Determine success.

        Rules:
        1. Base success if Judge0 status id == 3 (Accepted)
        2. If expected_output provided, compare against the LAST non-empty line of stdout
           (trimmed of whitespace & trailing newlines) to let users print steps.
        3. If no stdout or mismatch, fail.
        """
        if status_id != 3:
            return False
        if expected_output is None:
            return True
        if stdout is None:
            return False
        # Extract last non-empty line
        lines = [l.strip() for l in stdout.splitlines() if l.strip()]
        if not lines:
            return False
        return lines[-1] == expected_output.strip()
    
    async def get_languages(self) -> List[LanguageInfo]:
        """Get list of supported programming languages"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/languages",
                headers=self.headers
            )
            if response.status_code == 200:
                try:
                    languages_data = response.json()
                except Exception as e:
                    raise Exception(f"Failed to parse languages JSON: {e} body={response.text[:200]}")
                return [LanguageInfo(id=lang.get("id"), name=lang.get("name")) for lang in languages_data]
            # Enhanced diagnostics
            raise Exception(
                "Failed to fetch languages: "
                f"{response.status_code} body={response.text[:300]}"
            )
    
    async def get_statuses(self) -> List[Judge0Status]:
        """Get list of submission statuses"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/statuses",
                headers=self.headers
            )
            if response.status_code == 200:
                try:
                    statuses_data = response.json()
                except Exception as e:
                    raise Exception(f"Failed to parse statuses JSON: {e} body={response.text[:200]}")
                return [Judge0Status(id=status.get("id"), description=status.get("description"))
                        for status in statuses_data]
            raise Exception(
                "Failed to fetch statuses: "
                f"{response.status_code} body={response.text[:300]}"
            )
    
    async def submit_code(self, submission: CodeSubmissionCreate, user_id: Optional[str] = None) -> Judge0SubmissionResponse:
        judge0_request = Judge0SubmissionRequest(
            source_code=submission.source_code,
            language_id=submission.language_id,
            stdin=submission.stdin,
            expected_output=submission.expected_output
        )
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/submissions?base64_encoded=false&wait=false",
                headers=self.headers,
                json=judge0_request.model_dump(exclude_none=True)
            )
            
            if response.status_code == 201:
                result = response.json()
                judge0_response = Judge0SubmissionResponse(token=result["token"])
                
                # Optionally store in Supabase
                if user_id:
                    await self._store_submission(submission, user_id, judge0_response.token)
                
                return judge0_response
            else:
                raise Exception(f"Failed to submit code: {response.status_code} - {response.text}")
    
    async def get_submission_result(self, token: str) -> Judge0ExecutionResult:
        """Get execution result by token"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/submissions/{token}?base64_encoded=false",
                headers=self.headers
            )
            
            if response.status_code == 200:
                result = response.json()
                return Judge0ExecutionResult(**result)
            else:
                raise Exception(f"Failed to get result: {response.status_code}")
    
    async def execute_code_sync(self, submission: CodeSubmissionCreate, user_id: Optional[str] = None,
                               max_wait_time: int = 45, poll_interval: float = 1.0,
                               prefer_wait: bool = True) -> CodeExecutionResult:
        """Submit code and wait for result.

        prefer_wait: when True try Judge0 wait=true for immediate result (saves polling).
        max_wait_time: total seconds to poll if still queued/processing.
        poll_interval: seconds between polls.
        """

        if prefer_wait:
            # Direct wait submission (does not use stored submission because no token until result)
            judge0_request = Judge0SubmissionRequest(
                source_code=submission.source_code,
                language_id=submission.language_id,
                stdin=submission.stdin,
                expected_output=submission.expected_output
            )
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.base_url}/submissions?base64_encoded=false&wait=true",
                    headers=self.headers,
                    json=judge0_request.model_dump(exclude_none=True)
                )
            if resp.status_code == 201:
                data = resp.json()
                # Build pseudo Judge0ExecutionResult shape compatibility
                status = data.get("status") or {}
                language = data.get("language") or {"id": submission.language_id}
                execution_result = CodeExecutionResult(
                    stdout=data.get("stdout"),
                    stderr=data.get("stderr"),
                    compile_output=data.get("compile_output"),
                    execution_time=data.get("time"),
                    memory_used=data.get("memory"),
                    status_id=status.get("id", -1),
                    status_description=status.get("description", "unknown"),
                    language_id=language.get("id", submission.language_id),
                    success=self._compute_success(status.get("id"), data.get("stdout"), submission.expected_output),
                    created_at=datetime.utcnow()
                )
                # Store submission + result if user_id provided (create submission row first without token)
                if user_id:
                    # We still want a submission record; token may be absent in wait=true response
                    token = data.get("token")
                    if token:
                        await self._store_submission(submission, user_id, token)
                        await self._store_result(token, execution_result)
                return execution_result
            # fallback to polling path if wait=true not allowed

        judge0_response = await self.submit_code(submission, user_id)

        start_time = time.time()
        while time.time() - start_time < max_wait_time:
            result = await self.get_submission_result(judge0_response.token)
            if result.status["id"] not in [1, 2]:
                execution_result = CodeExecutionResult(
                    stdout=result.stdout,
                    stderr=result.stderr,
                    compile_output=result.compile_output,
                    execution_time=result.time,
                    memory_used=result.memory,
                    status_id=result.status.get("id", -1),
                    status_description=result.status.get("description", "unknown"),
                    language_id=(result.language or {}).get("id", submission.language_id),
                    success=self._compute_success(result.status.get("id"), result.stdout, submission.expected_output),
                    created_at=datetime.utcnow()
                )
                if user_id:
                    await self._store_result(judge0_response.token, execution_result)
                return execution_result
            await asyncio.sleep(poll_interval)
        raise Exception("Timeout waiting for execution result")
    
    async def _store_submission(self, submission: CodeSubmissionCreate, user_id: str, judge0_token: str):
        """Store submission using SQLAlchemy"""
        try:
            return judge0_repository.create_submission_sql(submission, user_id, judge0_token)
        except Exception as e:
            print(f"Error storing submission: {e}")
            raise e
    
    async def _store_result(self, judge0_token: str, result: CodeExecutionResult):
        """Store execution result using SQLAlchemy"""
        try:
            # Get submission by token
            submission = judge0_repository.get_submission_by_token_sql(judge0_token)
            if submission:
                # Create result
                return judge0_repository.create_result_sql(str(submission.id), result)
            else:
                print(f"No submission found for token: {judge0_token}")
        except Exception as e:
            print(f"Error storing result: {e}")
            raise e
    
    # Additional service methods using repository
    async def get_user_submissions(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all submissions for a user"""
        return await judge0_repository.get_user_submissions(user_id, limit)
    
    async def get_submission_with_results(self, submission_id: str) -> Optional[Dict[str, Any]]:
        """Get submission with its execution results"""
        return await judge0_repository.get_submission_with_results(submission_id)
    
    async def delete_user_submission(self, submission_id: str, user_id: str) -> bool:
        """Delete a submission (only if it belongs to the user)"""
        return await judge0_repository.delete_submission(submission_id, user_id)
    
    async def get_language_statistics(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get statistics about language usage"""
        return await judge0_repository.get_language_statistics(user_id)

#Create instance
judge0_service = Judge0Service()