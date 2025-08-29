from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date, timezone, timedelta
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
) -> SlideKey:
    d_local = given_at.astimezone(SA_TZ)
    season = season_from_date(d_local.date())
    week = week_from_date(semester_start, d_local.date())
    topic_slug = to_topic_slug(topic_name)
    ts = int(d_local.timestamp())
    unique = uuid.uuid4().hex[:8]
    # Note: bucket is already named 'slides', so do not prefix with 'slides/' here
    object_key = f"{season}/w{week:02d}/{topic_slug}/{ts}-{unique}-{original_filename}"
    return SlideKey(season=season, week=week, topic_slug=topic_slug, object_key=object_key)


def parse_week_topic_from_filename(filename: str) -> tuple[int | None, str | None]:
    """Best-effort parse of week number and topic from filenames like:
    Week1_Lecture_Variables_Loops.pptx or week10-dictionaries.pptx
    Returns (week:int|None, topic:str|None)
    """
    stem = filename
    # strip extension
    try:
        stem = os.path.splitext(filename)[0]
    except Exception:
        pass
    s = stem.strip()
    m = re.match(r"(?i)\s*week\s*(\d{1,2})[\s_\-]*?(?:lecture[\s_\-]*)?(.*)$", s)
    week_val: int | None = None
    topic_name: str | None = None
    if m:
        try:
            week_val = int(m.group(1))
        except Exception:
            week_val = None
        raw_topic = (m.group(2) or "").strip().replace("_", " ").replace("-", " ")
        topic_name = raw_topic if raw_topic else None
    return week_val, topic_name
