from __future__ import annotations

from typing import Optional, List, Dict, Any, Tuple

from app.features.judge0.schemas import CodeSubmissionCreate
from app.features.judge0.service import judge0_service


def _normalize_expected(expected: Optional[str]) -> Optional[str]:
    if expected is None:
        return None
    # Normalise newlines and trailing whitespace, keep last non-empty line
    s = expected.replace("\r\n", "\n")
    lines = [ln.rstrip() for ln in s.split("\n") if ln.strip()]
    if not lines:
        return None
    # Ensure we compare to a line without trailing spaces
    return lines[-1]


async def run_one(
    *,
    language_id: int,
    source: str,
    stdin: Optional[str] = None,
    expected: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a single snippet and return a normalised result dict.

    Returns keys: token, stdout, stderr, status_id, status_description, success, time, memory.
    """
    sub = CodeSubmissionCreate(
        source_code=source,
        language_id=language_id,
        stdin=stdin,
        expected_output=_normalize_expected(expected),
    )
    token, res = await judge0_service.execute_code_sync(sub)
    return {
        "token": token,
        "stdout": res.stdout,
        "stderr": res.stderr,
        "status_id": res.status_id,
        "status_description": res.status_description,
        "success": bool(res.success),
        "time": res.execution_time,
        "memory": res.memory_used,
    }


async def run_many(
    items: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Execute many snippets and return aligned list of result dicts.

    Each item supports keys: language_id, source, stdin, expected.
    """
    submissions: List[CodeSubmissionCreate] = []
    for it in items:
        submissions.append(CodeSubmissionCreate(
            source_code=it.get("source") or it.get("source_code") or "",
            language_id=int(it.get("language_id")),
            stdin=it.get("stdin"),
            expected_output=_normalize_expected(it.get("expected")),
        ))
    batch = await judge0_service.execute_batch(submissions)
    out: List[Dict[str, Any]] = []
    for (token, res) in batch:
        out.append({
            "token": token,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "status_id": res.status_id,
            "status_description": res.status_description,
            "success": bool(res.success),
            "time": res.execution_time,
            "memory": res.memory_used,
        })
    return out

