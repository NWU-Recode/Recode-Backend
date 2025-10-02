from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date, timezone, timedelta
from typing import Optional
import re, uuid, os

# Robust timezone handling: fall back to fixed UTC+2 if tzdata not present
try:
    from zoneinfo import ZoneInfo
    try:
        SA_TZ = ZoneInfo("Africa/Johannesburg")
    except Exception:
        SA_TZ = timezone(timedelta(hours=2))
except Exception:
    SA_TZ = timezone(timedelta(hours=2))


def to_topic_slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "topic"


def season_from_date(d: date) -> str:
    return f"{d.year}S1" if d.month <= 6 else f"{d.year}S2"


def week_from_date(semester_start: date, d: date) -> int:
    delta = (d - semester_start).days
    w = (delta // 7) + 1
    return max(1, min(12, w))


@dataclass
class SlideKey:
    season: str
    week: int
    topic_slug: str
    object_key: str


def build_slide_object_key(
    original_filename: str,
    topic_name: str,
    given_at: datetime,
    semester_start: date,
    semester_end: Optional[date] = None,
) -> SlideKey:
    d_local = given_at.astimezone(SA_TZ)
    target_date = d_local.date()
    if target_date < semester_start:
        target_date = semester_start
    if semester_end and target_date > semester_end:
        target_date = semester_end
    season = season_from_date(target_date)
    week = week_from_date(semester_start, target_date)
    topic_slug = to_topic_slug(topic_name)
    ts = int(d_local.timestamp())
    unique = uuid.uuid4().hex[:8]
    # Note: bucket is already named 'slides', so do not prefix with 'slides/' here
    object_key = f"{season}/w{week:02d}/{topic_slug}/{ts}-{unique}-{original_filename}"
    return SlideKey(season=season, week=week, topic_slug=topic_slug, object_key=object_key)


def parse_week_topic_from_filename(filename: str) -> tuple[int | None, str | None]:
    """Best-effort parse of topic from filename.

    IMPORTANT: week numbers must NOT be trusted from filenames. This parser now only
    returns a topic (if present). The application must compute week using
    `week_from_date(semester_start, given_date)` where `given_date` is derived from
    the upload timestamp or explicitly provided datetime.

    Returns (None, topic:str|None)
    """
    stem = filename
    # strip extension
    try:
        stem = os.path.splitext(filename)[0]
    except Exception:
        pass
    s = stem.strip()
    # Try to capture a trailing topic after an initial WeekN_ prefix but do not use the week
    m = re.match(r"(?i)\s*week\s*(\d{1,2})[\s_\-]*?(?:lecture[\s_\-]*)?(.*)$", s)
    topic_name: str | None = None
    if m:
        raw_topic = (m.group(2) or "").strip().replace("_", " ").replace("-", " ")
        topic_name = raw_topic if raw_topic else None
        return None, topic_name

    # Fallback: attempt to use the entire stem as a topic name if it contains words
    cleaned = re.sub(r"\s+", " ", s).strip()
    if cleaned:
        return None, cleaned
    return None, None
