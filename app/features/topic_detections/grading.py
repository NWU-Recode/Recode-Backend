from __future__ import annotations
from typing import Optional

def normalise_output(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    s = value.replace('\r\n', '\n').strip()
    lines = [ln.rstrip() for ln in s.split('\n') if ln.strip()]
    if not lines:
        return None
    return lines[-1].strip()

def is_correct(status_id: int | None, stdout: Optional[str], expected_output: Optional[str]) -> bool:
    if status_id != 3:  # Accepted
        return False
    if expected_output is None:
        return True
    exp = normalise_output(expected_output)
    act = normalise_output(stdout)
    return exp is not None and act is not None and exp == act

def map_app_status(status_id: int, correct: Optional[bool]) -> str:
    if status_id == 3:
        return "accepted" if correct else "wrong_answer"
    if status_id in {6, 7}:
        return "compile_error"
    if status_id in {4,5,8,9,10,11,12,13}:
        return "runtime_error"
    if status_id in {1,2}:
        return "pending"
    return "other_error"

__all__ = ["is_correct", "map_app_status", "normalise_output"]
