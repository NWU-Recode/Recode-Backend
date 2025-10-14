import asyncio
import json
import types
from datetime import datetime, timezone

from app.features.judge0.schemas import (
    CodeSubmissionCreate,
    CodeExecutionResult,
    Judge0ExecutionResult,
    Judge0SubmissionResponse,
)
from app.features.judge0.service import Judge0Service


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def test_execute_code_sync_backfills_stdout(monkeypatch):
    service = Judge0Service()
    service.base_url = "http://example.test"
    service.settings.judge0_timeout_s = 2

    async def fake_submit_code(submission):
        return Judge0SubmissionResponse(token="tok")

    async def fake_request(method, path, **kwargs):
        payload = {
            "token": "tok",
            "stdout": "",
            "stderr": None,
            "compile_output": None,
            "message": None,
            "time": "0.01",
            "memory": 128,
            "status": {"id": 4, "description": "Wrong Answer"},
            "language": {"id": 71},
        }
        return _FakeResponse(payload)

    async def fake_get_submission_result(token):
        return Judge0ExecutionResult(
            token=token,
            stdout="hello",
            stderr=None,
            compile_output=None,
            message=None,
            time="0.01",
            memory=128,
            status={"id": 4, "description": "Wrong Answer"},
            language={"id": 71},
        )

    monkeypatch.setattr(service, "submit_code", fake_submit_code)
    monkeypatch.setattr(service, "_request", fake_request)
    monkeypatch.setattr(service, "get_submission_result", fake_get_submission_result)

    submission = CodeSubmissionCreate(source_code="print('hi')", language_id=71)

    async def _run():
        return await service.execute_code_sync(submission)

    token, result = asyncio.run(_run())

    assert token == "tok"
    assert result.stdout == "hello"
    assert result.status_id == 4
    assert result.status_description == "Wrong Answer"


def test_submit_code_sends_expected_output(monkeypatch):
    service = Judge0Service()
    service.base_url = "http://example.test"
    captured: dict[str, object] = {}

    async def fake_request(method, path, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kwargs.get("json")
        return _FakeResponse({"token": "tok"}, status_code=201)

    monkeypatch.setattr(service, "_request", fake_request)

    submission = CodeSubmissionCreate(
        source_code="print('hi')",
        language_id=71,
        stdin="1 2",
        expected_output="3\n",
    )

    async def _run():
        return await service.submit_code(submission)

    response = asyncio.run(_run())

    assert response.token == "tok"
    assert captured["method"] == "POST"
    assert "json" in captured
    assert captured["json"]["expected_output"] == "3\n"


def test_execute_batch_small_concurrent(monkeypatch):
    service = Judge0Service()
    service.base_url = "http://example.test"

    submissions = [
        CodeSubmissionCreate(source_code=f"print({idx})", language_id=71, stdin=str(idx))
        for idx in range(4)
    ]

    started = {"count": 0}
    gate = asyncio.Event()

    async def fake_execute_code_sync(self, submission, fields="token,stdout"):
        idx = int(submission.stdin or 0)
        started["count"] += 1
        if started["count"] == len(submissions):
            gate.set()
        await gate.wait()
        result = CodeExecutionResult(
            submission_id=f"sub-{idx}",
            stdout=f"stdout-{idx}",
            stderr="",
            compile_output=None,
            execution_time="0.01",
            memory_used=64,
            status_id=3,
            status_description="Accepted",
            language_id=71,
            success=True,
            created_at=datetime.now(timezone.utc),
        )
        return f"tok-{idx}", result

    monkeypatch.setattr(
        service,
        "execute_code_sync",
        types.MethodType(fake_execute_code_sync, service),
    )

    async def _run():
        return await asyncio.wait_for(service.execute_batch(submissions), timeout=1)

    results = asyncio.run(_run())

    assert gate.is_set()
    assert started["count"] == len(submissions)
    assert [tok for tok, _ in results] == [f"tok-{idx}" for idx in range(len(submissions))]


def test_execute_batch_hydrates_stdout(monkeypatch):
    service = Judge0Service()
    service.base_url = "http://example.test"

    async def fake_submit_batch(submissions):
        return [f"tok-{idx}" for idx in range(len(submissions))]

    async def fake_get_batch_results(tokens, *, fields=None):
        results = {}
        for tok in tokens:
            results[tok] = Judge0ExecutionResult(
                token=tok,
                stdout="",
                stderr=None,
                compile_output=None,
                message=None,
                time="0.01",
                memory=64,
                status={"id": 4, "description": "Wrong Answer"},
                language={"id": 71},
            )
        return results

    async def fake_get_submission_result(token):
        return Judge0ExecutionResult(
            token=token,
            stdout=f"actual-{token}",
            stderr="",
            compile_output=None,
            message=None,
            time="0.02",
            memory=128,
            status={"id": 4, "description": "Wrong Answer"},
            language={"id": 71},
        )

    monkeypatch.setattr(service, "submit_batch", fake_submit_batch)
    monkeypatch.setattr(service, "get_batch_results", fake_get_batch_results)
    monkeypatch.setattr(service, "get_submission_result", fake_get_submission_result)

    submissions = [
        CodeSubmissionCreate(source_code="print('hi')", language_id=71)
        for _ in range(9)
    ]

    async def _run():
        return await service.execute_batch(submissions)

    results = asyncio.run(_run())

    assert len(results) == 9
    for idx, (tok, res) in enumerate(results):
        assert tok == f"tok-{idx}"
        assert res.stdout == f"actual-tok-{idx}"
        assert res.status_id == 4
