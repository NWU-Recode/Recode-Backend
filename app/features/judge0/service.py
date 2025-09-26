import httpx
import asyncio
import time
import hashlib
import random
import logging
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


class Judge0Service:
    def __init__(self):
        self.settings = get_settings()
        # Normalise base URL: prefer configured JUDGE0_URL / JUDGE0_BASE_URL
        base = (self.settings.judge0_api_url or "").strip()
        if base and not base.startswith("http://") and not base.startswith("https://"):
            # assume http if scheme omitted
            base = "http://" + base
        # If no explicit port provided, default to 2358 (common Judge0 CE port)
        if base:
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(base)
            netloc = parsed.netloc
            # If netloc does not include a port, append the default
            if ':' not in netloc:
                netloc = f"{netloc}:2358"
                parsed = parsed._replace(netloc=netloc)
                base = urlunparse(parsed)
        # strip trailing slash to make joining paths predictable
        self.base_url = base.rstrip("/")
        self.headers = {"Content-Type": "application/json"}
        if self.settings.judge0_api_key and self.settings.judge0_host:
            self.headers.update({
                "X-RapidAPI-Key": self.settings.judge0_api_key,
                "X-RapidAPI-Host": self.settings.judge0_host,
            })
        # Simple in-memory caches for static metadata endpoints
        from app.common import cache as _cache
        self._cache = _cache
        # Known archived/unsupported language ids on the EC2 Judge0 instance
        self._archived_ids = {28}
        self._python3_cache: Optional[int] = None
        # Logger for diagnostics
        self._logger = logging.getLogger(__name__)

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Internal helper to perform an HTTP request against the configured Judge0 base URL.

        Catches connection/timeouts and raises a descriptive Exception so callers can surface
        meaningful 5xx errors instead of ambiguous timeouts.
        """
        if not self.base_url:
            raise Exception("Judge0 base URL is not configured (JUDGE0_URL / JUDGE0_BASE_URL).")
        # Ensure path begins with /
        if not path.startswith("/"):
            path = "/" + path
        url = self.base_url.rstrip("/") + path
        # Mask sensitive header values for logging
        def _mask_headers(h: dict) -> dict:
            masked = {}
            for k, v in (h or {}).items():
                if k.lower() in ("x-rapidapi-key",):
                    masked[k] = "[REDACTED]"
                else:
                    masked[k] = v
            return masked
        try:
            self._logger.debug("Judge0 request: %s %s headers=%s", method, url, _mask_headers(self.headers))
        except Exception:
            # ensure logging never interferes with normal operation
            pass
        timeout = httpx.Timeout(connect=3.0, read=self.settings.judge0_timeout_s, write=5.0, pool=5.0)
        limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
                    resp = await client.request(method, url, headers=self.headers, **kwargs)
                return resp
            except (httpx.ConnectTimeout, httpx.ConnectError) as e:
                # Connection-level issues: retry a few times with backoff then raise a descriptive error
                if attempt < max_retries - 1:
                    backoff = 0.5 * (attempt + 1)
                    await asyncio.sleep(backoff)
                    continue
                raise Exception(f"Failed to connect to Judge0 at {self.base_url}: {e}") from e
            except Exception:
                # Re-raise any other errors (including parsing) for higher-level handling
                raise

    async def _resolve_python3_id(self) -> int:
        if self._python3_cache is not None:
            return self._python3_cache
        try:
            langs = await self.get_languages()
            # Prefer a Python 3.x language
            for lang in langs:
                name = (lang.name or "").lower()
                if name.startswith("python (3") or name.startswith("python 3"):
                    self._python3_cache = int(lang.id)
                    return self._python3_cache
        except Exception:
            pass
        # Fallback to common Python 3 id on Judge0 CE
        self._python3_cache = 71
        return 71

    async def _normalize_language_id(self, lang_id: Optional[int]) -> int:
        try:
            lid = int(lang_id) if lang_id is not None else 0
        except Exception:
            lid = 0
        if lid in self._archived_ids or lid <= 0:
            return await self._resolve_python3_id()
        return lid

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
        key = "judge0:languages"
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        resp = await self._request("GET", "/languages")
        if resp.status_code == 200:
            try:
                languages_data = resp.json()
            except Exception as e:
                raise Exception(f"Failed to parse languages JSON: {e} body={resp.text[:200]}")
            value = [LanguageInfo(id=lang.get("id"), name=lang.get("name")) for lang in languages_data]
            self._cache.set(key, value, ttl=3600)
            return value
        raise Exception(f"Failed to fetch languages: {resp.status_code} body={resp.text[:300]}")
    
    async def get_statuses(self) -> List[Judge0Status]:
        """Statuses."""
        key = "judge0:statuses"
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        resp = await self._request("GET", "/statuses")
        if resp.status_code == 200:
            try:
                statuses_data = resp.json()
            except Exception as e:
                raise Exception(f"Failed to parse statuses JSON: {e} body={resp.text[:200]}")
            value = [Judge0Status(id=status.get("id"), description=status.get("description"))
                    for status in statuses_data]
            self._cache.set(key, value, ttl=3600)
            return value
        raise Exception(f"Failed to fetch statuses: {resp.status_code} body={resp.text[:300]}")
    
    async def submit_code(self, submission: CodeSubmissionCreate) -> Judge0SubmissionResponse:
        norm_lang = await self._normalize_language_id(submission.language_id)
        judge0_request = Judge0SubmissionRequest(
            source_code=submission.source_code,
            language_id=norm_lang,
            stdin=submission.stdin
        )
        response = await self._request(
            "POST",
            "/submissions?base64_encoded=false&wait=false",
            json=judge0_request.model_dump(exclude_none=True),
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
        norm_lang = await self._normalize_language_id(submission.language_id)
        judge0_request = Judge0SubmissionRequest(
            source_code=submission.source_code,
            language_id=norm_lang,
            stdin=submission.stdin,
            expected_output=submission.expected_output if submission.expected_output else None,
        )
        response = await self._request(
            "POST",
            f"/submissions?base64_encoded=false&wait=true&fields={fields}",
            json=judge0_request.model_dump(exclude_none=True),
        )
        # Judge0 may return 200 or 201 for wait=true responses
        if response.status_code not in (200, 201):
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
        return token, exec_result
    
    async def get_submission_result(self, token: str) -> Judge0ExecutionResult:
        resp = await self._request("GET", f"/submissions/{token}?base64_encoded=false")
        if resp.status_code == 200:
            result = resp.json()
            return Judge0ExecutionResult(**result)
        raise Exception(f"Failed to get result: {resp.status_code} body={resp.text[:200]}")
    

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
        # Determine a deterministic submission_id string derived from the Judge0 token when available
        submission_id: str | None = None
        token_val = getattr(raw, 'token', None)
        if token_val:
            try:
                # Use SHA256 of the token and take first 16 hex digits -> stable id string
                submission_id = hashlib.sha256(token_val.encode()).hexdigest()[:16]
            except Exception:
                submission_id = str(uuid4())
        else:
            submission_id = str(uuid4())

        # created_at: if Judge0 didn't return a timestamp, use now
        created_at = getattr(raw, 'created_at', None)
        if created_at is None:
            created_at = datetime.utcnow()

        # Status description fallback: prefer explicit description from Judge0 result; if empty, consult cached statuses
        status_description = (raw.status or {}).get("description") if raw.status else None
        if not status_description:
            try:
                cached = self._cache.get("judge0:statuses")
                if cached:
                    # cached is a list of Judge0Status objects
                    desc_map = {s.id: s.description for s in cached}
                    status_description = desc_map.get(status_id) if status_id is not None else None
            except Exception:
                status_description = None
        if not status_description:
            status_description = "unknown"

        return CodeExecutionResult(
            submission_id=submission_id,
            stdout=raw.stdout,
            stderr=raw.stderr,
            compile_output=raw.compile_output,
            execution_time=raw.time,
            memory_used=raw.memory,
            status_id=status_id or -1,
            status_description=status_description,
            language_id=lang_id,
            success=success,
            created_at=created_at,
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
        while True:
            response = await self._request("GET", f"/submissions/{token}?base64_encoded=false")
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
        reqs: List[Dict[str, Any]] = []
        for s in submissions:
            norm_lang = await self._normalize_language_id(s.language_id)
            reqs.append(Judge0SubmissionRequest(
                source_code=s.source_code,
                language_id=norm_lang,
                stdin=s.stdin,
                expected_output=s.expected_output,
            ).model_dump(exclude_none=True))
        payload = {"submissions": reqs}
        resp = await self._request(
            "POST",
            "/submissions/batch?base64_encoded=false&wait=false",
            json=payload,
        )
        if resp.status_code != 201:
            raise Exception(f"Batch submit failed: {resp.status_code} {resp.text[:200]}")
        data = resp.json()
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
        token_param = ",".join(tokens)
        resp = await self._request(
            "GET",
            f"/submissions/batch?tokens={token_param}&base64_encoded=false",
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
        timeout_seconds: Optional[float] = 60,
        poll_interval: float = 1.0,
    ) -> List[tuple[str, CodeExecutionResult]]:
        """Submit a batch then poll until all finished; returns list aligned to original order."""
        if len(submissions) <= 8:
            out: List[tuple[str, CodeExecutionResult]] = []
            for sub in submissions:
                tok, res = await self.execute_code_sync(sub)
                out.append((tok, res))
            return out

        tokens = await self.submit_batch(submissions)
        pending = set(tokens)
        start = time.time()
        latest: Dict[str, CodeExecutionResult] = {}
        while pending and (timeout_seconds is None or time.time() - start < timeout_seconds):
            try:
                batch = await self.get_batch_results(list(pending))
            except Exception:
                batch = {}
            progressed = False
            if batch:
                for tok, raw in batch.items():
                    status_id = raw.status.get("id") if raw.status else None
                    if status_id not in [1, 2]:
                        idx = tokens.index(tok)
                        sub = submissions[idx]
                        latest[tok] = self._to_code_execution_result(raw, sub.expected_output, sub.language_id)
                        if tok in pending:
                            pending.discard(tok)
                            progressed = True
            if pending:
                for tok in list(pending):
                    try:
                        raw = await self.get_submission_result(tok)
                        status_id = raw.status.get("id") if raw.status else None
                        if status_id not in [1, 2]:
                            idx = tokens.index(tok)
                            sub = submissions[idx]
                            latest[tok] = self._to_code_execution_result(raw, sub.expected_output, sub.language_id)
                            pending.discard(tok)
                            progressed = True
                    except Exception:
                        pass
            if not pending:
                break
            if not progressed:
                await asyncio.sleep(poll_interval)
        if pending and timeout_seconds is not None:
            raise TimeoutError("Batch execution timed out")
        return [(tok, latest[tok]) for tok in tokens]

    async def execute_quick_code(self, submission: QuickCodeSubmission) -> CodeExecutionResult:
        judge0_response = await self.submit_code(submission)
        token = judge0_response.token

        while True:
            response = await self._request("GET", f"/submissions/{token}?base64_encoded=false")
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
