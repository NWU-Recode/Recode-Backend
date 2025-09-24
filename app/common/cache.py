from __future__ import annotations

import os
import time
from typing import Any, Optional

_DEFAULT_TTL = int(os.getenv("READ_CACHE_SECONDS", os.getenv("AUTH_ME_CACHE_SECONDS", "60")))
_DISABLED = os.getenv("READ_CACHE_DISABLED", "false").lower() == "true"

_STORE: dict[str, tuple[Any, float]] = {}

def get(key: str) -> Any | None:
    if _DISABLED:
        return None
    now = time.time()
    item = _STORE.get(key)
    if not item:
        return None
    value, exp = item
    if now < exp:
        return value
    try:
        _STORE.pop(key, None)
    except Exception:
        pass
    return None

def set(key: str, value: Any, ttl: Optional[int] = None) -> None:
    if _DISABLED:
        return
    ttl_s = int(ttl if ttl is not None else _DEFAULT_TTL)
    _STORE[key] = (value, time.time() + max(1, ttl_s))

def clear(prefix: Optional[str] = None) -> None:
    if prefix is None:
        _STORE.clear()
    else:
        keys = [k for k in _STORE.keys() if k.startswith(prefix)]
        for k in keys:
            _STORE.pop(k, None)

