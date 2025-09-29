from __future__ import annotations

import json
from pathlib import Path
from datetime import date, timedelta
from typing import Dict, Any

# Store demo state alongside scripts folder so it survives restarts but is easy to find.
STATE_FILE = Path(__file__).resolve().parents[2] / "scripts" / "demo_time_state.json"


def _read_state() -> Dict[str, Any]:
    try:
        if not STATE_FILE.exists():
            return {"offset_weeks": 0, "modules": {}}
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        # normalize
        return {
            "offset_weeks": int(data.get("offset_weeks", 0)),
            "modules": {k: int(v) for k, v in (data.get("modules") or {}).items()},
        }
    except Exception:
        return {"offset_weeks": 0, "modules": {}}


def _write_state(state: Dict[str, Any]) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state), encoding="utf-8")
    except Exception:
        # best-effort: ignore write failures in demo mode
        pass


def get_demo_week_offset() -> int:
    return int(_read_state().get("offset_weeks", 0))


def set_demo_week_offset(offset: int) -> int:
    offset_val = int(offset or 0)
    state = _read_state()
    state["offset_weeks"] = offset_val
    _write_state(state)
    return offset_val


def add_demo_week_offset(delta: int) -> int:
    cur = get_demo_week_offset()
    new = int(cur + int(delta or 0))
    set_demo_week_offset(new)
    return new


def clear_demo_week_offset() -> None:
    set_demo_week_offset(0)


# Module-scoped offsets
def get_demo_week_offset_for_module(module_code: str) -> int:
    state = _read_state()
    return int(state.get("modules", {}).get(module_code, 0))


def set_demo_week_offset_for_module(module_code: str, offset: int) -> int:
    state = _read_state()
    modules = state.get("modules", {})
    modules[module_code] = int(offset or 0)
    state["modules"] = modules
    _write_state(state)
    return modules[module_code]


def add_demo_week_offset_for_module(module_code: str, delta: int) -> int:
    cur = get_demo_week_offset_for_module(module_code)
    new = int(cur + int(delta or 0))
    set_demo_week_offset_for_module(module_code, new)
    return new


def clear_demo_week_offset_for_module(module_code: str) -> None:
    state = _read_state()
    modules = state.get("modules", {})
    if module_code in modules:
        modules.pop(module_code, None)
    state["modules"] = modules
    _write_state(state)


def apply_demo_offset_to_semester_start(semester_start: date, module_code: str | None = None) -> date:
    """Return an adjusted semester_start that accounts for demo offset.

    If a module_code is provided and has a configured offset, use that. Otherwise use the global offset.
    We move the semester_start earlier so the system thinks time has advanced by that many weeks.
    """
    try:
        if module_code:
            offset = get_demo_week_offset_for_module(module_code)
        else:
            offset = get_demo_week_offset()
        if not offset:
            return semester_start
        return semester_start - timedelta(weeks=int(offset))
    except Exception:
        return semester_start
