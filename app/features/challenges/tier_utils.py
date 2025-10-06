from __future__ import annotations

from typing import Optional

BASE_TIER = "base"
LEGACY_BASE_ALIASES = {"plain", "common", "weekly", BASE_TIER, ""}


def normalise_challenge_tier(value: Optional[str]) -> Optional[str]:
    """Return the canonical challenge tier string.

    Legacy data may still reference tiers such as "plain" or "common" –
    when encountered we coerce them to "base" so that the rest of the code
    can rely on a single naming convention. Empty values return None.
    """

    if value is None:
        return None
    text = str(value).strip().lower()
    if text in LEGACY_BASE_ALIASES:
        return BASE_TIER
    return text or None
