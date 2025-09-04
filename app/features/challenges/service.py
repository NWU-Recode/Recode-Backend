"""Restart challenge generation service (minimal).

Implements only AI-backed creation of:
 - Weekly challenge (5 ordered difficulties: bronze, bronze, silver, silver, gold)
 - Special challenges: ruby (every 2nd week), emerald (every 4th week), diamond (week >= 12)

Behaviour:
 - Idempotent unless force=True (which deletes existing by slug then regenerates)
 - Returns challenge + inserted questions (with test cases) to caller
 - No attempts / submissions / scoring logic
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
from uuid import uuid4
import json

from app.DB.supabase import get_supabase
from app.features.challenges.ai.generator import generate_question_spec  # existing async generator (single question spec)

WEEKLY_PATTERN = ["bronze", "bronze", "silver", "silver", "gold"]

def _slug(kind: str, week: int) -> str:
    return f"{kind}-week-{week}"

def _points(diff: Optional[str]) -> int:
    return {"bronze": 10, "silver": 20, "gold": 40, "ruby": 50, "emerald": 60, "diamond": 100}.get((diff or "").lower(), 10)

def _weekly_prompt(week: int) -> str:
    return (
        f"Week {week} challenge set. Provide EXACTLY 5 questions as a JSON array (not wrapped in extra text). "
        "Order: bronze, bronze, silver, silver, gold. Each object keys: title, question_text, difficulty, "
        "input_format, output_format, sample_input_output (object with sample_input, sample_output), "
        "test_cases (array of objects each with input, output)."
    )

def _special_prompt(kind: str, week: int) -> str:
    base = f"Generate ONE {kind} challenge for week {week}. Return a single JSON object with same keys as weekly questions."
    if kind == "ruby":
        base += " Advanced bronze/silver bridge difficulty."
    elif kind == "emerald":
        base += " Harder than ruby; focus on optimization."
    else:
        base += " Capstone difficulty integrating multiple topics."
    return base

def _allowed_special(kind: str, week: int) -> bool:
    return (
        (kind == "ruby" and week % 2 == 0) or
        (kind == "emerald" and week % 4 == 0) or
        (kind == "diamond" and week >= 12)
    )

async def _delete_by_slug(slug: str) -> None:
    client = await get_supabase()
    client.table("challenges").delete().eq("slug", slug).execute()

async def _insert_challenge(kind: str, week: int, lecturer_id: Optional[int]) -> Dict[str, Any]:
    payload = {
        "id": str(uuid4()),
        "title": f"Week {week} Challenge" if kind == "weekly" else f"{kind.title()} Challenge Week {week}",
        "description": f"Auto-generated {kind} challenge for week {week}.",
        "kind": kind,
        "slug": _slug(kind, week),
        "status": "published",
        "lecturer_creator": lecturer_id,
        "topic_id": None,
    }
    client = await get_supabase()
    res = client.table("challenges").insert(payload).execute()
    return res.data[0] if getattr(res, 'data', None) else payload

async def _insert_question(challenge_id: str, q: Dict[str, Any], order: int) -> Dict[str, Any]:
    tests_raw = q.get("test_cases") or []
    q_payload = {
        "id": str(uuid4()),
        "challenge_id": challenge_id,
        "title": q.get("title") or f"Question {order+1}",
        "question_text": q.get("question_text") or q.get("body") or "",
        "difficulty": q.get("difficulty"),
        "input_format": q.get("input_format"),
        "output_format": q.get("output_format"),
        "sample_input_output": json.dumps(q.get("sample_input_output")),
        "order_index": order,
        "points": _points(q.get("difficulty")),
    }
    client = await get_supabase()
    res = client.table("questions").insert(q_payload).execute()
    inserted = res.data[0] if getattr(res, 'data', None) else q_payload
    tests_insert = []
    for idx, t in enumerate(tests_raw):
        if isinstance(t, dict):
            _in = t.get("input") or t.get("in") or ""
            _out = t.get("output") or t.get("expected") or ""
        elif isinstance(t, (list, tuple)) and len(t) == 2:
            _in, _out = t
        else:
            continue
        tests_insert.append({
            "id": str(uuid4()),
            "question_id": inserted["id"],
            "input": _in,
            "output": _out,
            "order_index": idx,
        })
    if tests_insert:
        client.table("question_tests").insert(tests_insert).execute()
    inserted["test_cases"] = tests_insert
    return inserted

async def generate_weekly_challenge(week: int, lecturer_id: Optional[int], force: bool = False) -> Dict[str, Any]:
    slug = _slug("weekly", week)
    if force:
        await _delete_by_slug(slug)
    client = await get_supabase()
    existing = client.table("challenges").select("id, slug").eq("slug", slug).execute().data
    if existing:
        ch_id = existing[0]["id"]
        qs = client.table("questions").select("*", count="exact").eq("challenge_id", ch_id).order("order_index").execute().data
        return {"challenge": existing[0], "questions": qs, "regenerated": False}

    # The existing generator returns single question spec; call per difficulty.
    spec_list = []
    for diff in WEEKLY_PATTERN:
        spec = await generate_question_spec([], week, None, kind="common", tier=diff)
        spec_list.append({
            "title": spec.get("title") or f"{diff.title()} Question",
            "question_text": spec.get("question_text") or spec.get("prompt") or "",
            "difficulty": diff,
            "input_format": spec.get("input_format"),
            "output_format": spec.get("output_format"),
            "sample_input_output": spec.get("sample_input_output"),
            "test_cases": [
                {"input": t.get("input"), "output": t.get("expected")}
                for t in (spec.get("tests") or [])
            ],
        })

    challenge = await _insert_challenge("weekly", week, lecturer_id)
    inserted = []
    for idx, q in enumerate(spec_list):
        inserted.append(await _insert_question(challenge["id"], q, idx))
    return {"challenge": challenge, "questions": inserted, "regenerated": True}

async def generate_special_challenge(kind: str, week: int, lecturer_id: Optional[int], force: bool = False) -> Dict[str, Any]:
    kind = kind.lower()
    if kind not in {"ruby", "emerald", "diamond"}:
        return {"error": "invalid special kind"}
    if not _allowed_special(kind, week):
        return {"error": f"{kind} challenge not scheduled for week {week}"}
    slug = _slug(kind, week)
    if force:
        await _delete_by_slug(slug)
    client = await get_supabase()
    existing = client.table("challenges").select("id, slug").eq("slug", slug).execute().data
    if existing and not force:
        ch_id = existing[0]["id"]
        qs = client.table("questions").select("*", count="exact").eq("challenge_id", ch_id).order("order_index").execute().data
        return {"challenge": existing[0], "questions": qs, "regenerated": False}

    spec = await generate_question_spec([], week, None, kind=kind, tier=kind)
    mapped = {
        "title": spec.get("title") or f"{kind.title()} Question",
        "question_text": spec.get("question_text") or spec.get("prompt") or "",
        "difficulty": kind,
        "input_format": spec.get("input_format"),
        "output_format": spec.get("output_format"),
        "sample_input_output": spec.get("sample_input_output"),
        "test_cases": [
            {"input": t.get("input"), "output": t.get("expected")}
            for t in (spec.get("tests") or [])
        ],
    }
    challenge = await _insert_challenge(kind, week, lecturer_id)
    q_inserted = await _insert_question(challenge["id"], mapped, 0)
    return {"challenge": challenge, "questions": [q_inserted], "regenerated": True}

async def generate_semester_challenges(lecturer_id: Optional[int], force: bool = False) -> Dict[str, Any]:
    """Generate all 12 weekly challenges (and scheduled specials) for the semester.

    Returns a mapping: week -> { weekly: {...}, ruby?, emerald?, diamond? }
    """
    semester: Dict[str, Any] = {}
    for week in range(1, 13):
        week_bundle: Dict[str, Any] = {"weekly": await generate_weekly_challenge(week, lecturer_id, force)}
        if week % 2 == 0:
            week_bundle["ruby"] = await generate_special_challenge("ruby", week, lecturer_id, force)
        if week % 4 == 0:
            week_bundle["emerald"] = await generate_special_challenge("emerald", week, lecturer_id, force)
        if week >= 12:
            week_bundle["diamond"] = await generate_special_challenge("diamond", week, lecturer_id, force)
        semester[str(week)] = week_bundle
    return semester
