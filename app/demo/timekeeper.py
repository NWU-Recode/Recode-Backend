from datetime import timedelta, date
from typing import Optional

# Simple in-memory demo offsets (process-local). Not persistent — just to satisfy imports and basic behavior.
_global_offset_weeks: int = 0
_module_offsets: dict[str, int] = {}


def apply_demo_offset_to_semester_start(sem_start: date, module_code: Optional[str] = None) -> date:
    """Return semester_start adjusted by demo offset (module-specific if provided, else global)."""
    offset = _module_offsets.get(module_code) if module_code else None
    if offset is None:
        offset = _global_offset_weeks
    try:
        return sem_start + timedelta(weeks=int(offset))
    except Exception:
        return sem_start


# Global offsets
def add_demo_week_offset(delta: int) -> int:
    global _global_offset_weeks
    _global_offset_weeks += int(delta)
    return _global_offset_weeks


def set_demo_week_offset(value: int) -> int:
    global _global_offset_weeks
    _global_offset_weeks = int(value)
    return _global_offset_weeks


def clear_demo_week_offset() -> int:
    global _global_offset_weeks
    _global_offset_weeks = 0
    return _global_offset_weeks


def get_demo_week_offset() -> int:
    return _global_offset_weeks


# Module-scoped offsets
def add_demo_week_offset_for_module(module_code: str, delta: int) -> int:
    v = _module_offsets.get(module_code, 0) + int(delta)
    _module_offsets[module_code] = v
    return v


def set_demo_week_offset_for_module(module_code: str, value: int) -> int:
    _module_offsets[module_code] = int(value)
    return _module_offsets[module_code]


def clear_demo_week_offset_for_module(module_code: str) -> int:
    _module_offsets.pop(module_code, None)
    return 0


def get_demo_week_offset_for_module(module_code: str) -> Optional[int]:
    return _module_offsets.get(module_code)
