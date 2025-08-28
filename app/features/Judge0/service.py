import httpx
import asyncio
import time
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import uuid4

from app.Core.config import get_settings
from .schemas import (
    CodeSubmissionCreate,
    CodeSubmissionResponse,
    Judge0SubmissionRequest,
    Judge0SubmissionResponse,
    Judge0ExecutionResult,
    CodeExecutionResult,
    LanguageInfo,
    Judge0Status,
    QuickCodeSubmission
)
from app.features.submissions.schemas import SubmissionCreate
from app.features.submissions.service import submission_service

class Judge0Service:
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.judge0_api_url
        self.headers = {"Content-Type": "application/json"}
        if self.settings.judge0_api_key and self.settings.judge0_host:
            self.headers.update({
                "X-RapidAPI-Key": self.settings.judge0_api_key,
                "X-RapidAPI-Host": self.settings.judge0_host,
            })

    @staticmethod
    def _compute_success(status_id: int | None, stdout: str | None, expected_output: str | None) -> bool:
        # Accepted status required
        if status_id != 3:
            return False
        if expected_output is None:
            return True
        if stdout is None:
            return False
        def _norm(s: str) -> str | None:
            if s is None:
                return None
            # Normalise newlines, trim, split, take last non-empty
            s2 = s.replace('\r\n', '\n').strip()
            lines = [ln.rstrip() for ln in s2.split('\n') if ln.strip()]
            if not lines:
                return None
            return lines[-1].strip()
        expected = _norm(expected_output)
        actual = _norm(stdout)
        if expected is None or actual is None:
            return False
        return actual == expected
    
    async def get_languages(self) -> List[LanguageInfo]:
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
        """Statuses."""
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
    
    async def submit_code(self, submission: CodeSubmissionCreate) -> Judge0SubmissionResponse:
        judge0_request = Judge0SubmissionRequest(
            source_code=submission.source_code,
            language_id=submission.language_id,
            stdin=submission.stdin
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
                
                return judge0_response
            else:
                raise Exception(f"Failed to submit code: {response.status_code} - {response.text}")

    async def submit_code_wait(
        self,
        submission: CodeSubmissionCreate,
        fields: str = "token,stdout,stderr,status_id,time,memory,language"
    ) -> Judge0ExecutionResult:
        """Submit code with wait=true to get immediate result (single-call execution).

        This is used for per-question instant submits to avoid polling overhead.
        """
        judge0_request = Judge0SubmissionRequest(
            source_code=submission.source_code,
            language_id=submission.language_id,
            stdin=submission.stdin,
            expected_output=submission.expected_output if submission.expected_output else None,
        )
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/submissions?base64_encoded=false&wait=true&fields={fields}",
                headers=self.headers,
                json=judge0_request.model_dump(exclude_none=True),
            )
        if response.status_code != 201:
            raise Exception(f"Failed waited submit: {response.status_code} {response.text[:200]}")
        data = response.json()
        # Ensure token present (Judge0 returns it even with fields subset if included)
        if "token" not in data:
            # Fallback: issue secondary GET by location header? For simplicity raise.
            raise Exception("Waited submit missing token in response")
        # Conform to Judge0ExecutionResult shape by injecting minimal status structure if only status_id present
        if "status" not in data and "status_id" in data:
            data["status"] = {"id": data["status_id"], "description": data.get("status_description", "")}
        return Judge0ExecutionResult(**data)

    async def execute_code_sync(
        self,
        submission: CodeSubmissionCreate,
        fields: str = "token,stdout,stderr,status_id,time,memory,language"
    ) -> tuple[str, CodeExecutionResult]:
        """Waited single-call execution returning (token, CodeExecutionResult) with no persistence.

        Mirrors spec 'execute_code_sync(wait=True)'. Internally uses submit_code_wait.
        """
        waited = await self.submit_code_wait(submission, fields=fields)
        token = waited.token  # type: ignore[attr-defined]
        exec_result = self._to_code_execution_result(waited, submission.expected_output, submission.language_id)
        return token, exec_result

    async def submit_question_run(
        self,
        submission: CodeSubmissionCreate,
        user_id: str,
        fields: str = "token,stdout,stderr,status_id,time,memory,language"
    ) -> tuple[str, CodeExecutionResult]:
        """High-level per-question run that waits, normalises, and persists both submission and result.

        Returns (judge0_token, CodeExecutionResult)
        """
        waited = await self.submit_code_wait(submission, fields=fields)
        token = waited.token  # type: ignore[attr-defined]
        exec_result = self._to_code_execution_result(waited, submission.expected_output, submission.language_id)
        # Persist submission row (status set based on final status id)
        status_label = "completed" if exec_result.status_id not in [1, 2] else "processing"
        sub_create = SubmissionCreate(
            source_code=submission.source_code,
            language_id=submission.language_id,
            stdin=submission.stdin,
            expected_output=submission.expected_output,
            # question_id injected by higher layer (QuestionService) if needed; left None here
        )
        stored_sub = await submission_service.store_submission(sub_create, user_id, token)
        # Update status if needed
        # Persist result row
        await submission_service.store_result(token, exec_result)
        return token, exec_result
    
    async def get_submission_result(self, token: str) -> Judge0ExecutionResult:
        #Result by token.
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
    
    # NOTE: Persistence & higher-level orchestration removed; endpoints or submissions service handle storage & polling.

    def _to_code_execution_result(
        self,
        raw: Judge0ExecutionResult,
        expected_output: str | None,
        language_fallback: int | None = None,
    ) -> CodeExecutionResult:
        lang_id = None
        if raw.language and isinstance(raw.language, dict):
            lang_id = raw.language.get("id")
        if lang_id is None:
            lang_id = language_fallback or -1
        status_id = raw.status.get("id") if raw.status else None
        success = self._compute_success(status_id, raw.stdout, expected_output)
        return CodeExecutionResult(
            stdout=raw.stdout,
            stderr=raw.stderr,
            compile_output=raw.compile_output,
            execution_time=raw.time,
            memory_used=raw.memory,
            status_id=status_id or -1,
            status_description=(raw.status or {}).get("description", "unknown"),
            language_id=lang_id,
            success=success,
        )

    async def execute_code(
        self,
        submission: CodeSubmissionCreate,
        timeout_seconds: int = 45,
        poll_interval: float = 1.0,
    ) -> str:
        """Submit code, poll until finished, and return only the stdout.

        This method does not require expected_output and focuses solely on the code's output.
        """
        token = (await self.submit_code(submission)).token
        start = time.time()
        async with httpx.AsyncClient() as client:
            while True:
                response = await client.get(
                    f"{self.base_url}/submissions/{token}",
                    headers=self.headers
                )
                if response.status_code == 200:
                    result = response.json()
                    if result["status"]["id"] in [1, 2]:  # In Queue or Processing
                        await asyncio.sleep(1)
                        continue
                    return result.get("stdout")
                else:
                    raise Exception(f"Failed to fetch submission result: {response.status_code} - {response.text}")

    async def execute_with_token(
        self,
        submission: CodeSubmissionCreate,
        timeout_seconds: int = 45,
        poll_interval: float = 1.0,
    ) -> tuple[str, CodeExecutionResult]:
        """Like execute_code but also returns the Judge0 token.

        Useful for persisting question attempts where we want to keep the token reference.
        """
        token_resp = await self.submit_code(submission)
        token = token_resp.token
        start = time.time()
        while time.time() - start < timeout_seconds:
            res = await self.get_submission_result(token)
            status_id = res.status.get("id") if res.status else None
            if status_id not in [1, 2]:
                return token, self._to_code_execution_result(res, submission.expected_output, submission.language_id)
            await asyncio.sleep(poll_interval)
        raise TimeoutError("Judge0 execution timed out")

    # -------- Batch operations --------
    async def submit_batch(self, submissions: List[CodeSubmissionCreate]) -> List[str]:
        """Submit multiple code submissions at once (returns list of tokens in same order)."""
        payload = {
            "submissions": [
                Judge0SubmissionRequest(
                    source_code=s.source_code,
                    language_id=s.language_id,
                    stdin=s.stdin,
                    expected_output=s.expected_output,
                ).model_dump(exclude_none=True) for s in submissions
            ]
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/submissions/batch?base64_encoded=false&wait=false",
                headers=self.headers,
                json=payload,
            )
        if resp.status_code != 201:
            raise Exception(f"Batch submit failed: {resp.status_code} {resp.text[:200]}")
        data = resp.json()
        # Accept either {"submission_tokens":[{"token":..}]} or list
        tokens: List[str] = []
        if isinstance(data, dict) and "submission_tokens" in data:
            for item in data["submission_tokens"]:
                tok = item.get("token") if isinstance(item, dict) else None
                if tok:
                    tokens.append(tok)
        elif isinstance(data, list):
            for item in data:
                tok = item.get("token") if isinstance(item, dict) else None
                if tok:
                    tokens.append(tok)
        if len(tokens) != len(submissions):
            # Still return what we have but flag mismatch
            raise Exception("Token count mismatch in batch response")
        return tokens

    async def get_batch_results(self, tokens: List[str]) -> Dict[str, Judge0ExecutionResult]:
        """Fetch multiple submissions by tokens (returns mapping token -> result)."""
        if not tokens:
            return {}
        # Judge0 expects comma separated tokens
        token_param = ",".join(tokens)
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/submissions/batch?tokens={token_param}&base64_encoded=false",
                headers=self.headers,
            )
        if resp.status_code != 200:
            raise Exception(f"Batch get failed: {resp.status_code} {resp.text[:200]}")
        arr = resp.json()
        results: Dict[str, Judge0ExecutionResult] = {}
        if isinstance(arr, list):
            for item in arr:
                tok = item.get("token") if isinstance(item, dict) else None
                if tok:
                    results[tok] = Judge0ExecutionResult(**item)
        return results

    async def execute_batch(
        self,
        submissions: List[CodeSubmissionCreate],
        timeout_seconds: int = 60,
        poll_interval: float = 1.0,
    ) -> List[tuple[str, CodeExecutionResult]]:
        """Submit a batch then poll until all finished; returns list aligned to original order."""
        tokens = await self.submit_batch(submissions)
        pending = set(tokens)
        start = time.time()
        latest: Dict[str, CodeExecutionResult] = {}
        while pending and time.time() - start < timeout_seconds:
            batch = await self.get_batch_results(list(pending))
            for tok, raw in batch.items():
                status_id = raw.status.get("id") if raw.status else None
                if status_id not in [1, 2]:
                    # find corresponding submission for expected output & language
                    idx = tokens.index(tok)
                    sub = submissions[idx]
                    latest[tok] = self._to_code_execution_result(raw, sub.expected_output, sub.language_id)
                    pending.discard(tok)
            if pending:
                await asyncio.sleep(poll_interval)
        if pending:
            raise TimeoutError("Batch execution timed out")
        return [(tok, latest[tok]) for tok in tokens]

    async def execute_quick_code(self, submission: QuickCodeSubmission) -> CodeExecutionResult:
        judge0_response = await self.submit_code(submission)
        token = judge0_response.token

        async with httpx.AsyncClient() as client:
            while True:
                response = await client.get(
                    f"{self.base_url}/submissions/{token}",
                    headers=self.headers
                )
                if response.status_code == 200:
                    result = response.json()
                    if result["status"]["id"] in [1, 2]:  # In Queue or Processing
                        await asyncio.sleep(1)
                        continue
                    return CodeExecutionResult(
                        stdout=result.get("stdout"),
                        stderr=result.get("stderr"),
                        compile_output=result.get("compile_output"),
                        execution_time=result.get("time"),
                        memory_used=result.get("memory"),
                        status_id=result["status"]["id"],
                        status_description=result["status"]["description"],
                        language_id=submission.language_id,
                        success=result["status"]["id"] == 3,
                        created_at=datetime.utcnow()
                    )
                else:
                    raise Exception(f"Failed to fetch submission result: {response.status_code} - {response.text}")

judge0_service = Judge0Service()