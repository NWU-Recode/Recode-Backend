from __future__ import annotations

from typing import List, Dict, Any


def _norm_line(s: str | None) -> str | None:
    if s is None:
        return None
    s2 = s.replace('\r\n', '\n').strip()
    lines = [ln.rstrip() for ln in s2.split('\n') if ln.strip()]
    if not lines:
        return None
    return lines[-1].strip()


def compare_output_against_tests(output: str | None, tests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compare a single output string against a list of test dicts.

    Returns a list of dicts: { test_id, visibility, expected, passed }
    This mirrors Judge0 success heuristic (last non-empty line equality).
    """
    results: List[Dict[str, Any]] = []
    actual = _norm_line(output)
    for t in tests:
        expected = _norm_line(t.get("expected") if isinstance(t, dict) else None)
        passed = False
        if expected is None and actual is not None:
            passed = False
        elif expected is None and actual is None:
            passed = False
        else:
            passed = (actual == expected)
        results.append({
            "test_id": t.get("id"),
            "visibility": (t.get("visibility") or "public").lower(),
            "expected": t.get("expected"),
            "passed": passed,
        })
    return results
