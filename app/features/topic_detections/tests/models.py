from sqlalchemy import Column, Integer, String, Enum, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.DB.base import Base
import enum

class QuestionTestVisibility(enum.Enum):
    public = "public"
    hidden = "hidden"

class QuestionTest(Base):
    __tablename__ = 'question_test'
    __table_args__ = (
        Index('ix_question_test_question_id', 'question_id'),
    )

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("question.id"), nullable=False)
    input = Column(String, nullable=False)
    expected = Column(String, nullable=False)
    visibility = Column(Enum(QuestionTestVisibility), nullable=False, index=True)

    question = relationship("Question", back_populates="tests")
Rules

Season format: YYYYS1 (Jan–Jun) or YYYYS2 (Jul–Dec) — adjust if your uni defines semesters differently.

Week numbering: w01…w12, derived from a configured semester_start_date.

Path: slides/{season}/w{week}/{topic_slug}/{ts}-{uuid}-{original_filename}

Timezone: Africa/Johannesburg.

Python (FastAPI backend, supabase-py v2)
# app/adapters/supabase_client.py
import os
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # service role (backend only)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# app/features/slides/pathing.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, date, timezone, timedelta
from zoneinfo import ZoneInfo
import re, time, uuid

SA_TZ = ZoneInfo("Africa/Johannesburg")

def to_topic_slug(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "topic"

def season_from_date(d: date) -> str:
    # Change month split if your semester boundaries differ.
    return f"{d.year}S1" if d.month <= 6 else f"{d.year}S2"

def week_from_date(semester_start: date, d: date) -> int:
    delta = (d - semester_start).days
    # week 1 for days 0..6, week 2 for 7..13, etc.
    w = (delta // 7) + 1
    return max(1, min(12, w))  # clamp to 1..12 for MVP

@dataclass
class SlideKey:
    season: str
    week: int
    topic_slug: str
    object_key: str  # full storage key (path+filename)

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