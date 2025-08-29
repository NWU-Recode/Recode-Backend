from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from zoneinfo import ZoneInfo
import re, uuid

SA_TZ = ZoneInfo("Africa/Johannesburg")


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
    object_key = f"slides/{season}/w{week:02d}/{topic_slug}/{ts}-{unique}-{original_filename}"
    return SlideKey(season=season, week=week, topic_slug=topic_slug, object_key=object_key)

