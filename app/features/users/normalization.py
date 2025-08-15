"""User normalization utilities.

Goals:
1. Provide stable defaults for optional fields even if the DB row omits them.
2. Tolerate slight schema drift / renamed keys (e.g. older "name" -> "full_name").
3. Parse Supabase ISO datetime strings into ``datetime`` objects.
4. Sanitize/trim simple string fields.
5. Ensure role & flags have safe fallbacks (avoid KeyError / None surprises).

This allows higher layers to treat returned objects uniformly via the `User` schema.
"""
from typing import Any, Dict, Optional
from datetime import datetime

from .schemas import User

# Defaults injected if missing from raw row
USER_DEFAULTS: Dict[str, Any] = {
    "full_name": None,
    "avatar_url": None,
    "phone": None,
    "bio": None,
    "role": "user",
    "is_active": True,
    "is_superuser": False,
    "email_verified": False,
    "last_sign_in": None,
    "user_metadata": None,
}

_DT_FIELDS = ("created_at", "updated_at", "last_sign_in")
_STRING_TRIM_FIELDS = ("full_name", "avatar_url", "phone", "bio")

def _coerce_datetimes(data: Dict[str, Any]) -> None:
    for key in _DT_FIELDS:
        val = data.get(key)
        if isinstance(val, str):
            try:
                data[key] = datetime.fromisoformat(val.replace("Z", "+00:00"))
            except ValueError:
                # Keep original string if parsing fails
                pass

def _trim_strings(data: Dict[str, Any]) -> None:
    for key in _STRING_TRIM_FIELDS:
        v = data.get(key)
        if isinstance(v, str):
            trimmed = v.strip()
            data[key] = trimmed or None  # normalize empty -> None

def _apply_aliases(data: Dict[str, Any]) -> None:
    # Older / alternative field names mapping
    if not data.get("full_name") and data.get("name"):
        data["full_name"] = data.get("name")

def normalize_user(raw: Dict[str, Any]) -> User:
    """Convert a raw Supabase user dict into a fully-populated `User` model.

    Steps:
        - merge defaults
        - apply alias mapping
        - trim strings
        - parse datetime fields
        - enforce role fallback
    """
    if raw is None:
        raise ValueError("Cannot normalize None user")

    # Shallow copy + defaults
    data: Dict[str, Any] = {**USER_DEFAULTS, **raw}

    _apply_aliases(data)
    _trim_strings(data)
    _coerce_datetimes(data)

    # Guaranteed role fallback
    role = data.get("role") or USER_DEFAULTS["role"]
    data["role"] = str(role)

    return User(**data)  # type: ignore[arg-type]

def maybe_normalize_user(raw: Optional[Dict[str, Any]]) -> Optional[User]:
    """Return normalized user or None."""
    return normalize_user(raw) if raw else None
