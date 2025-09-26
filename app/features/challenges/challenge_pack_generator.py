from __future__ import annotations

import os
import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from jsonschema import ValidationError, validate
except Exception:  # pragma: no cover - optional runtime dependency
    class ValidationError(Exception):
        pass

    def validate(instance, schema):
        # jsonschema not installed in this environment; skip validation but log a warning at runtime.
        import logging
        logging.getLogger(__name__).warning("jsonschema not available: skipping model response validation")
        return None

from app.DB.supabase import get_supabase
from app.features.challenges.model_runtime.bedrock_client import invoke_model
from app.features.challenges.templates.strings import get_fallback_payload

DEFAULT_TOPICS = [
    "variables",
    "conditionals",
    "loops",
    "functions",
    "lists",
]

POINTS_BY_DIFFICULTY = {
    "Bronze": 10,
    "Silver": 20,
    "Gold": 30,
    "Ruby": 40,
    "Emerald": 60,
    "Diamond": 100,
}

BASE_DISTRIBUTION = ["Bronze", "Bronze", "Silver", "Silver", "Gold"]


QUESTION_SCHEMA = {
    "type": "object",
    "required": ["challenge_set_title", "questions"],
    "properties": {
        "challenge_set_title": {"type": "string"},
        "questions": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": [
                    "title",
                    "question_text",
                    "difficulty_level",
                    "starter_code",
                    "reference_solution",
                    "tests",
                ],
                "properties": {
                    "title": {"type": "string"},
                    "question_text": {"type": "string"},
                    "difficulty_level": {"type": "string"},
                    "starter_code": {"type": "string"},
                    "reference_solution": {"type": "string"},
                    "tests": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["input", "expected"],
                            "properties": {
                                "input": {"type": "string"},
                                "expected": {"type": "string"},
                                "visibility": {"type": "string"},
                            },
                            "additionalProperties": True,
                        },
                    },
                },
                "additionalProperties": True,
            },
        },
    },
    "additionalProperties": True,
}

logger = logging.getLogger(__name__)

@dataclass
class TopicContext:
    week: int
    module_code: Optional[str]
    topic_id: Optional[str]
    topic_title: str
    topic_slug: Optional[str]
    prompt_topics: List[str]
    topic_ids_used: List[str] = field(default_factory=list)
    topic_titles_used: List[str] = field(default_factory=list)
    topic_history: List[Dict[str, Any]] = field(default_factory=list)
    topic_week_span: tuple[int, int] | None = None

    def joined_topics(self) -> str:
        raw_items = [t.strip() for t in self.prompt_topics if t and str(t).strip()]
        extra_titles = [str(t).strip() for t in self.topic_titles_used if str(t).strip()]
        items = raw_items + extra_titles
        if not items:
            items = DEFAULT_TOPICS
        unique: Dict[str, str] = {}
        for item in items:
            key = item.lower()
            if key not in unique:
                unique[key] = item
        return ", ".join(unique.values())

    def history_summary(self) -> str:
        if not self.topic_history:
            return f"- Week {self.week}: {self.topic_title}"
        lines: List[str] = []
        for entry in sorted(self.topic_history, key=lambda e: e.get("week") or 0, reverse=True):
            week_value = entry.get("week")
            if isinstance(week_value, int) and week_value > 0:
                week_label = f"Week {week_value}"
            else:
                week_label = "Week"
            title = str(entry.get("title") or "").strip()
            keywords = [
                str(k).strip()
                for k in entry.get("keywords", [])
                if str(k).strip()
            ]
            seen_kw = set()
            dedup_keywords: List[str] = []
            for kw in keywords:
                key = kw.lower()
                if key in seen_kw:
                    continue
                seen_kw.add(key)
                dedup_keywords.append(kw)
            details = title
            if dedup_keywords:
                if details:
                    extras = [kw for kw in dedup_keywords if kw.lower() != details.lower()]
                    if extras:
                        details = f"{details} ({', '.join(extras)})"
                else:
                    details = ", ".join(dedup_keywords)
            if not details:
                details = "General review"
            lines.append(f"- {week_label}: {details}")
        return "\n".join(lines) if lines else f"- Week {self.week}: {self.topic_title}"

    def week_window_label(self) -> str:
        if self.topic_week_span:
            start, end = self.topic_week_span
            if start and end:
                if start == end:
                    return f"Week {start}"
                return f"Weeks {start}-{end}"
        return f"Week {self.week}"



def _slugify(value: str) -> str:
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "challenge"


def _ensure_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(v).strip() for v in parsed if str(v).strip()]
        except json.JSONDecodeError:
            return [value]
    return []



TOPIC_WINDOW_BY_TIER = {
    "base": 1,
    "ruby": 2,
    "emerald": 4,
    "diamond": None,
}

TOPIC_LIMIT_BY_TIER = {
    "base": 1,
    "ruby": 2,
    "emerald": 4,
    "diamond": 12,
}


def _normalise_topic_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text


def _safe_week_number(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _trim_week_prefix(title: str) -> str:
    cleaned = title.strip()
    if ":" in cleaned:
        head, tail = cleaned.split(":", 1)
        if head.strip().lower().startswith("week"):
            return tail.strip() or cleaned
    return cleaned


def _extract_keywords_from_topic_row(row: Dict[str, Any]) -> List[str]:
    keywords: List[str] = []
    primary = _normalise_topic_string(row.get("detected_topic"))
    if primary:
        keywords.append(primary)
    for key in ("detected_subtopics", "subtopics"):
        keywords.extend(_ensure_list(row.get(key)))
    title_val = _normalise_topic_string(row.get("title"))
    if title_val:
        keywords.append(_trim_week_prefix(title_val))
    slug_val = _normalise_topic_string(row.get("slug"))
    if slug_val:
        keywords.append(slug_val.replace("-", " "))
    return keywords


async def _collect_topic_rows(
    client,
    *,
    week: int,
    module_code: Optional[str],
    window_weeks: Optional[int],
    max_rows: Optional[int],
) -> List[Dict[str, Any]]:
    # select all columns to avoid PostgREST schema-cache errors if columns differ
    query = client.table("topic").select("*")
    if module_code:
        query = query.eq("module_code_slidesdeck", module_code)
    try:
        query = query.order("week", desc=True)
        query = query.order("created_at", desc=True)
    except Exception:
        try:
            query = query.order("id", desc=True)
        except Exception:
            pass
    fetch_limit = max_rows or 24
    if window_weeks:
        fetch_limit = max(fetch_limit, window_weeks * 4)
    try:
        resp = await query.limit(fetch_limit).execute()
    except Exception:
        resp = await query.execute()
    rows = resp.data or []
    filtered: List[Dict[str, Any]] = []
    seen_ids: set = set()
    for row in rows:
        rid = row.get("id")
        rid_key = str(rid) if rid is not None else None
        if rid_key and rid_key in seen_ids:
            continue
        row_week = _safe_week_number(row.get("week"))
        if row_week > week:
            continue
        filtered.append(row)
        if rid_key:
            seen_ids.add(rid_key)
    filtered.sort(key=lambda r: (_safe_week_number(r.get("week")), str(r.get("created_at") or "")))
    if window_weeks is not None:
        min_week = max(1, week - window_weeks + 1)
        filtered = [row for row in filtered if _safe_week_number(row.get("week")) >= min_week]
    if max_rows is not None and len(filtered) > max_rows:
        filtered = filtered[-max_rows:]
    return filtered


async def _fetch_topic_context(
    week: int,
    slide_stack_id: Optional[int] = None,
    module_code: Optional[str] = None,
    tier: str = "base",
) -> TopicContext:
    client = await get_supabase()
    tier_key = (tier or "base").lower()
    window_weeks = TOPIC_WINDOW_BY_TIER.get(tier_key, 1)
    max_rows = TOPIC_LIMIT_BY_TIER.get(tier_key, 12)

    topic_id: Optional[str] = None
    prompt_topics: List[str] = []
    topic_title = f"Week {week} Topic"
    topic_slug: Optional[str] = None
    module_value = module_code
    topic_rows: List[Dict[str, Any]] = []

    if slide_stack_id is not None:
        # select all columns to avoid schema mismatches
        resp = await client.table("slide_extractions").select("*").eq("id", slide_stack_id).limit(1).execute()
        rows = resp.data or []
        if rows:
            row = rows[0]
            if row.get("topic_id"):
                topic_id = str(row.get("topic_id"))
            if not module_value and row.get("module_code"):
                module_value = row.get("module_code")
            # detected_subtopics/detected_topic may not exist in schema; use safe getters
            prompt_topics.extend(_ensure_list(row.get("detected_subtopics")))
            detected_topic = row.get("detected_topic")
            if detected_topic:
                prompt_topics.append(str(detected_topic))
            try:
                slide_week = int(row.get("week_number"))
                if slide_week > 0:
                    week = slide_week
            except (TypeError, ValueError):
                pass

    topic_rows = await _collect_topic_rows(
        client,
        week=week,
        module_code=module_value,
        window_weeks=window_weeks,
        max_rows=max_rows,
    )

    if topic_id and all(str(r.get("id")) != topic_id for r in topic_rows):
        try:
            # fetch full row by id
            t_resp = await client.table("topic").select("*").eq("id", topic_id).limit(1).execute()
            t_rows = t_resp.data or []
            if t_rows:
                topic_rows.append(t_rows[0])
        except Exception:
            pass

    topic_rows.sort(key=lambda r: (_safe_week_number(r.get("week")), str(r.get("created_at") or "")))

    topic_ids_used: List[str] = []
    topic_titles_used: List[str] = []
    history_by_week: Dict[int, Dict[str, Any]] = {}
    min_week_seen: Optional[int] = None
    max_week_seen: Optional[int] = None
    for row in topic_rows:
        rid = row.get("id")
        if rid is not None:
            rid_str = str(rid)
            if rid_str not in topic_ids_used:
                topic_ids_used.append(rid_str)
        week_value = _safe_week_number(row.get("week"))
        if week_value > 0:
            if min_week_seen is None or week_value < min_week_seen:
                min_week_seen = week_value
            if max_week_seen is None or week_value > max_week_seen:
                max_week_seen = week_value
        title_val = row.get("title") or row.get("detected_topic")
        cleaned_title = _trim_week_prefix(str(title_val)) if title_val else ""
        if cleaned_title and cleaned_title not in topic_titles_used:
            topic_titles_used.append(cleaned_title)
        row_keywords_raw = _extract_keywords_from_topic_row(row)
        prompt_topics.extend(row_keywords_raw)
        dedup_keywords: List[str] = []
        seen_kw = set()
        for kw in row_keywords_raw:
            normalised_kw = _normalise_topic_string(kw)
            if not normalised_kw:
                continue
            key_kw = normalised_kw.lower()
            if key_kw in seen_kw:
                continue
            seen_kw.add(key_kw)
            dedup_keywords.append(normalised_kw)
        if week_value > 0:
            entry = history_by_week.setdefault(
                week_value,
                {"week": week_value, "title": None, "keywords": []},
            )
            if cleaned_title and not entry.get("title"):
                entry["title"] = cleaned_title
            for kw in dedup_keywords:
                if kw and all(str(existing).lower() != kw.lower() for existing in entry["keywords"]):
                    entry["keywords"].append(kw)
        if not module_value:
            module_value = row.get("module_code_slidesdeck") or module_value

    if topic_titles_used:
        for title in topic_titles_used:
            if title and all(title.lower() != str(existing).lower() for existing in prompt_topics if isinstance(existing, str)):
                prompt_topics.append(title)

    topic_history = [history_by_week[week] for week in sorted(history_by_week, reverse=True)]
    topic_week_span = (
        (min_week_seen, max_week_seen)
        if min_week_seen is not None and max_week_seen is not None
        else None
    )

    primary_row: Optional[Dict[str, Any]] = None
    if topic_id:
        primary_row = next((row for row in topic_rows if str(row.get("id")) == str(topic_id)), None)
    if primary_row is None:
        for row in topic_rows:
            if _safe_week_number(row.get("week")) == week:
                primary_row = row
                break
    if primary_row is None and topic_rows:
        primary_row = topic_rows[-1]

    if primary_row:
        topic_title_candidate = primary_row.get("title") or primary_row.get("detected_topic")
        if topic_title_candidate:
            topic_title = str(topic_title_candidate)
        topic_slug_candidate = primary_row.get("slug")
        if topic_slug_candidate:
            topic_slug = str(topic_slug_candidate)
        if primary_row.get("id"):
            topic_id = str(primary_row.get("id"))
        if not module_value:
            module_value = primary_row.get("module_code_slidesdeck") or module_value

    cleaned_prompt: List[str] = []
    seen_keys: set = set()
    for item in prompt_topics:
        normalised = _normalise_topic_string(item)
        if not normalised:
            continue
        key = normalised.lower()
        if key in seen_keys:
            continue
        seen_keys.add(key)
        cleaned_prompt.append(normalised)
    if not cleaned_prompt:
        cleaned_prompt = DEFAULT_TOPICS

    if not topic_ids_used and topic_id:
        topic_ids_used = [topic_id]

    context = TopicContext(
        week=week,
        module_code=module_value,
        topic_id=str(topic_id) if topic_id else None,
        topic_title=topic_title,
        topic_slug=topic_slug,
        prompt_topics=cleaned_prompt,
        topic_ids_used=topic_ids_used,
        topic_titles_used=topic_titles_used,
        topic_history=topic_history,
        topic_week_span=topic_week_span,
    )
    return context


def _load_template(kind: str) -> str:
    templates = {
        "common": "base.txt",
        "base": "base.txt",
        "ruby": "ruby.txt",
        "emerald": "emerald.txt",
        "diamond": "diamond.txt",
    }
    name = templates.get(kind, "base.txt")
    candidate_dirs = [
        Path(__file__).parent / "prompts",
        Path(__file__).parent.parent / "prompts",
    ]
    for base_dir in candidate_dirs:
        path = base_dir / name
        if path.is_file():
            try:
                return path.read_text(encoding="utf-8")
            except Exception as exc:
                logger.warning("Failed to read prompt template %s: %s", path, exc)
    logger.warning("Prompt template %s not found; using minimal fallback", name)
    return "Generate a set of programming questions for week {{week_number}} covering {{topic_title}}. Topics: {{topics_list}}."


def _render_prompt(template: str, context: TopicContext) -> str:
    prompt = template
    topics_joined = context.joined_topics()
    prompt = prompt.replace("{{week_number}}", str(context.week))
    prompt = prompt.replace("{{topic_title}}", context.topic_title)
    prompt = prompt.replace("{{topic_window}}", context.week_window_label())
    prompt = prompt.replace("{{topics_list}}", topics_joined)
    prompt = prompt.replace("{{topic_history}}", context.history_summary())
    topics_count = len([item for item in topics_joined.split(",") if item.strip()])
    prompt = prompt.replace("{{topics_count}}", str(topics_count))
    return prompt


def _normalise_question(kind: str, question: Dict[str, Any], expected_difficulty: Optional[str]) -> Dict[str, Any]:
    result = dict(question)

    raw_difficulty = question.get("difficulty_level")
    difficulty = str(raw_difficulty).strip().title() if raw_difficulty else ""
    if expected_difficulty:
        difficulty = expected_difficulty
    elif difficulty:
        pass
    elif kind in {"ruby", "emerald", "diamond"}:
        difficulty = kind.title()
    else:
        difficulty = "Bronze"
    result["difficulty_level"] = difficulty

    result["starter_code"] = str(question.get("starter_code", ""))
    result["reference_solution"] = str(question.get("reference_solution", ""))
    if "question_text" in question:
        result["question_text"] = str(question.get("question_text", ""))
    if "title" in question:
        result["title"] = str(question.get("title", ""))

    tests = question.get("tests") or []
    normalised_tests: List[Dict[str, str]] = []
    for index, test in enumerate(tests):
        if not isinstance(test, dict):
            continue
        visibility = str(test.get("visibility", "public" if index == 0 else "private")).lower()
        if visibility not in {"public", "private"}:
            visibility = "private"
        normalised_tests.append(
            {
                "input": str(test.get("input", "")),
                "expected": str(test.get("expected", "")),
                "visibility": visibility,
            }
        )
    while len(normalised_tests) < 3:
        visibility = "public" if not normalised_tests else "private"
        normalised_tests.append({"input": "", "expected": "", "visibility": visibility})
    if normalised_tests:
        normalised_tests[0]["visibility"] = "public"
        for idx in range(1, len(normalised_tests)):
            normalised_tests[idx]["visibility"] = "private"
    result["tests"] = normalised_tests
    return result


def _normalise_questions(kind: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    questions = payload.get("questions", [])
    if kind in {"common", "base"}:
        if len(questions) < 5:
            raise ValueError("Model response did not include 5 questions for base/common payload")
        selected = questions[:5]
        return [
            _normalise_question(kind, selected[i], BASE_DISTRIBUTION[i])
            for i in range(5)
        ]
    if not questions:
        raise ValueError(f"Model response did not include questions for tier {kind}")
    return [_normalise_question(kind, questions[0], kind.title())]


async def _call_bedrock(kind: str, context: TopicContext) -> Dict[str, Any]:
    template = _load_template(kind)
    prompt = _render_prompt(template, context)
    # Optional test-mode: if GENERATOR_FAKE=1 use the local fallback payload
    if os.environ.get("GENERATOR_FAKE", "0") in {"1", "true", "True"}:
        return get_fallback_payload(kind, context.week, context.topic_title)

    max_attempts = 2
    last_error: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            result = await invoke_model(prompt)
            if isinstance(result, str):
                result = json.loads(result)
            validate(instance=result, schema=QUESTION_SCHEMA)
            return result
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            last_error = exc
            logger.warning(
                "Model response validation failed (attempt %s/%s) for tier %s: %s",
                attempt,
                max_attempts,
                kind,
                exc,
            )
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Model invocation failed (attempt %s/%s) for tier %s: %s",
                attempt,
                max_attempts,
                kind,
                exc,
            )
    logger.warning(
        "Using fallback challenge template for tier %s after %s model failures. Last error: %s",
        kind,
        max_attempts,
        last_error,
    )
    return get_fallback_payload(kind, context.week, context.topic_title)


async def _insert_challenge(
    client,
    *,
    tier: str,
    context: TopicContext,
    challenge_title: str,
    challenge_description: str,
    lecturer_id: Optional[int],
) -> Dict[str, Any]:
    if lecturer_id is None:
        raise ValueError("lecturer_id is required to insert challenge")

    module_part = _slugify(context.module_code or "module")
    # Use 'base' as the user-facing tier; legacy DB may use 'plain' for slugging
    tier_slug = "plain" if tier == "base" else _slugify(tier)
    slug = f"{module_part}-w{context.week:02d}-{tier_slug}"
    # Map to schema: weekly vs special
    is_weekly = tier == "base"
    challenge_type_value = "weekly" if is_weekly else "special"
    # For special challenges we set tier to the tier name (ruby/emerald/etc.)
    # Keep DB-level sentinel as 'plain' for legacy storage only when inserting;
    # but API consumers will see 'base' due to normalization in repository.
    tier_value = None if is_weekly else ("plain" if tier == "base" else tier)

    # Always compute an idempotency key for the challenge (used for dedup and returned to client).
    key_source = "|".join([
        str(context.topic_id or ""),
        str(context.module_code or ""),
        str(context.week),
        tier,
    ])
    idempotency_key = hashlib.sha256(key_source.encode("utf-8")).hexdigest()[:16]

    async def _fetch_existing(field: str, value: Any) -> Optional[Dict[str, Any]]:
        # Only attempt to fetch by a field if value is present
        if value in {None, ""}:
            return None
        # Prevent querying for columns that may not exist in the PostgREST schema cache
        try:
            has_col = await _table_has_column("challenges", field)
        except Exception:
            has_col = False
        if not has_col:
            return None
        try:
            resp = await client.table("challenges").select("*").eq(field, value).limit(1).execute()
            rows = resp.data or []
            return rows[0] if rows else None
        except Exception:
            return None

    async def _table_has_column(table: str, column: str) -> bool:
        try:
            resp = await client.table(table).select(column).limit(1).execute()
            # if the call succeeded without raising, assume column exists
            return True
        except Exception:
            return False

    # Check whether the challenges table supports idempotency_key
    supports_idempotency = await _table_has_column("challenges", "idempotency_key")
    existing = None
    if supports_idempotency:
        existing = await _fetch_existing("idempotency_key", idempotency_key)
        if existing is None:
            existing = await _fetch_existing("slug", slug)
            if existing and not existing.get("idempotency_key"):
                try:
                    update = await client.table("challenges").update({"idempotency_key": idempotency_key}).eq("id", existing.get("id")).execute()
                    if update.data:
                        existing = update.data[0]
                except Exception:
                    pass
    else:
        # schema doesn't support idempotency_key: fall back to slug-based de-duplication
        existing = await _fetch_existing("slug", slug)
    if existing:
        # Ensure the existing row payload includes the computed idempotency_key so callers can see it.
        try:
            if isinstance(existing, dict):
                existing.setdefault("idempotency_key", idempotency_key)
        except Exception:
            pass
        return existing

    payload = {
        "title": challenge_title,
        "description": challenge_description,
        "status": "draft",
        # map to provided schema: module_id (uuid) expected
    }

    # Resolve module_id from module_code if available
    module_id_value = None
    try:
        if context.module_code:
            mresp = await client.table("modules").select("id").eq("code", context.module_code).limit(1).execute()
            mrows = mresp.data or []
            if mrows:
                module_id_value = mrows[0].get("id")
    except Exception:
        module_id_value = None

    if module_id_value:
        payload["module_id"] = module_id_value
    else:
        # Keep a reference to the module code in a fallback field if module_id isn't resolvable
        payload.setdefault("module_code", context.module_code)

    # Set challenge_type and weekly/special-specific fields
    payload["challenge_type"] = challenge_type_value
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    # release_date and due_date
    payload["release_date"] = now.isoformat()
    payload["due_date"] = (now + timedelta(days=7)).isoformat()

    if is_weekly:
        payload["week_number"] = int(context.week or 0) or None
        # weekly per schema requires tier null and trigger_event null (omit them)
    else:
        # special challenges: include tier and a trigger_event marker
        payload["tier"] = tier if tier is not None else None
        payload["week_number"] = None
        payload["trigger_event"] = {"auto_generated": True, "week": context.week}
    # Only include optional columns if the DB table supports them
    try:
        if await _table_has_column("challenges", "idempotency_key"):
            payload["idempotency_key"] = idempotency_key
    except Exception:
        pass
    try:
        if await _table_has_column("challenges", "slug"):
            payload.setdefault("slug", slug)
    except Exception:
        pass
    try:
        if await _table_has_column("challenges", "topic_id") and context.topic_id:
            payload["topic_id"] = context.topic_id
    except Exception:
        pass
    try:
        if await _table_has_column("challenges", "lecturer_creator") and lecturer_id is not None:
            payload["lecturer_creator"] = int(lecturer_id)
    except Exception:
        pass
    if supports_idempotency:
        payload["idempotency_key"] = idempotency_key
    resp = await client.table("challenges").insert(payload).execute()
    if not resp.data:
        raise ValueError(f"Failed to create challenge for tier {tier}")
    record = resp.data[0]
    # Attach idempotency_key to the returned record dictionary (even if it couldn't be persisted).
    try:
        if isinstance(record, dict):
            record.setdefault("idempotency_key", idempotency_key)
    except Exception:
        pass
    return record


async def _insert_tests(client, question_id: Any, tests: List[Dict[str, str]]) -> None:
    # Persist generated tests into the canonical `question_tests` table.
    # Map fields: input -> input, expected -> expected_output, visibility preserved, valid defaults to True.
    for test in tests:
        payload = {
            "question_id": question_id,
            "input": test.get("input", ""),
            "expected_output": test.get("expected", ""),
            "visibility": test.get("visibility", "public"),
            # Only include slug in payload if the DB table actually supports it
            # "slug": slug,
        }
        # Try inserting into question_tests; fall back to legacy `tests` table if question_tests doesn't exist.
        try:
            await client.table("question_tests").insert(payload).execute()
        except Exception:
            await client.table("tests").insert({
                "question_id": question_id,
                "input": test.get("input", ""),
                "expected": test.get("expected", ""),
                "visibility": test.get("visibility", "public"),
            }).execute()


async def _insert_question(
    client,
    *,
    challenge_id: Any,
    question: Dict[str, Any],
    order_index: int,
) -> Dict[str, Any]:
    difficulty = str(question.get("difficulty_level", "Bronze"))
    points = POINTS_BY_DIFFICULTY.get(difficulty.title(), 10)
    tests = question.get("tests", [])
    public_expected = next((t.get("expected") for t in tests if (t.get("visibility") == "public")), None)
    if public_expected is None and tests:
        public_expected = tests[0].get("expected")
    if public_expected is not None:
        public_expected = str(public_expected)

    language_id = question.get("language_id")
    if isinstance(language_id, int):
        resolved_language = language_id
    else:
        language_key = str(question.get("language", "")).lower()
        resolved_language = {"python": 71, "python3": 71, "py": 71}.get(language_key, 71)

    title_value = str(question.get("title", "")).strip() or "Problem"
    question_text = str(question.get("question_text", ""))
    starter_code = str(question.get("starter_code", ""))
    reference_solution = str(question.get("reference_solution", ""))

    payload = {
        "challenge_id": challenge_id,
        "language_id": resolved_language,
        "expected_output": public_expected,
        "points": points,
        "starter_code": starter_code,
        "max_time_ms": 2000,
        "max_memory_kb": 256000,
        "tier": difficulty.lower(),
        "question_text": question_text,
        "reference_solution": reference_solution,
        "question_number": order_index,
        "title": title_value,
    }
    resp = await client.table("questions").insert(payload).execute()
    if not resp.data:
        raise ValueError("Failed to insert question")
    record = resp.data[0]
    await _insert_tests(client, record.get("id"), tests)
    return record


class ChallengePackGenerator:
    def __init__(self, week: int, slide_stack_id: Optional[int] = None, module_code: Optional[str] = None, lecturer_id: Optional[int] = None):
        self.week = week
        self.slide_stack_id = slide_stack_id
        self.module_code = module_code
        self.lecturer_id = lecturer_id
        self._client = None

    async def _client_handle(self):
        if self._client is None:
            self._client = await get_supabase()
        return self._client


    async def generate(self) -> Dict[str, Any]:
        client = await self._client_handle()

        if self.lecturer_id is None:
            raise ValueError("lecturer_id is required to persist generated challenges")

        created: Dict[str, Optional[Dict[str, Any]]] = {"base": None, "ruby": None, "emerald": None, "diamond": None}
        tiers = ["base", "ruby", "emerald", "diamond"]
        tier_contexts: Dict[str, TopicContext] = {}

        async def _context_for(tier: str) -> TopicContext:
            key = tier.lower()
            existing = tier_contexts.get(key)
            if existing is None:
                existing = await _fetch_topic_context(
                    self.week,
                    slide_stack_id=self.slide_stack_id,
                    module_code=self.module_code,
                    tier=key,
                )
                tier_contexts[key] = existing
            return existing

        async def _generate_and_store(tier: str) -> Optional[Dict[str, Any]]:
            try:
                context = await _context_for(tier)
                payload = await _call_bedrock(tier, context)
                questions = _normalise_questions(tier, payload)
                challenge = await _insert_challenge(
                    client,
                    tier=tier,
                    context=context,
                    challenge_title=payload.get("challenge_set_title") or f"Week {self.week} {tier.title()} Challenge",
                    challenge_description=f"Auto-generated {tier} challenge for Week {self.week} covering {context.topic_title}.",
                    lecturer_id=self.lecturer_id,
                )
                existing_q = await client.table("questions").select("id").eq("challenge_id", challenge.get("id")).execute()
                existing_ids = [str(r.get("id")) for r in (existing_q.data or []) if r.get("id")]
                stored_questions = []
                if existing_ids:
                    stored_questions = [{"id": qid} for qid in existing_ids]
                else:
                    for idx, question in enumerate(questions, start=1):
                        stored = await _insert_question(
                            client,
                            challenge_id=challenge.get("id"),
                            question=question,
                            order_index=idx,
                        )
                        stored_questions.append(stored)
                return {
                    "challenge_id": str(challenge.get("id")),
                    "question_ids": [str(q.get("id")) for q in stored_questions],
                    "topics_used": context.joined_topics(),
                    "topic_ids_used": context.topic_ids_used,
                }
            except Exception as exc:
                print(f"[challenge-generator] Skipped {tier}: {exc}")
                return None

        results = await asyncio.gather(*(_generate_and_store(t) for t in tiers))
        for tier_name, tier_result in zip(tiers, results):
            created[tier_name] = tier_result

        topics_used_by_tier: Dict[str, str] = {}
        topic_ids_by_tier: Dict[str, List[str]] = {}
        topic_titles_by_tier: Dict[str, List[str]] = {}
        for tier_name in tiers:
            context = tier_contexts.get(tier_name)
            if context:
                topics_used_by_tier[tier_name] = context.joined_topics()
                topic_ids_by_tier[tier_name] = context.topic_ids_used
                topic_titles_by_tier[tier_name] = context.topic_titles_used

        base_context = tier_contexts.get("base")
        module_value = base_context.module_code if base_context else self.module_code
        topic_id_value = base_context.topic_id if base_context else None

        return {
            "week": self.week,
            "topics_used": topics_used_by_tier.get("base") or "",
            "topics_used_by_tier": topics_used_by_tier,
            "topic_id": topic_id_value,
            "topic_ids_by_tier": topic_ids_by_tier,
            "topic_titles_by_tier": topic_titles_by_tier,
            "module_code": module_value,
            "created": created,
            "status": "completed",
        }


def _tier_from_kind(tier: str) -> str:
    return "base" if tier == "common" else tier


async def generate_challenges_with_model(
    week: int,
    slide_stack_id: Optional[int] = None,
    module_code: Optional[str] = None,
    lecturer_id: Optional[int] = None,
) -> Dict[str, Any]:
    generator = ChallengePackGenerator(
        week, slide_stack_id=slide_stack_id, module_code=module_code, lecturer_id=lecturer_id
    )
    return await generator.generate()



async def generate_tier_preview(
    tier: str,
    week: int,
    slide_stack_id: Optional[int] = None,
    module_code: Optional[str] = None,
) -> Dict[str, Any]:
    internal_tier = _tier_from_kind(tier)
    context = await _fetch_topic_context(week, slide_stack_id=slide_stack_id, module_code=module_code, tier=internal_tier)
    payload = await _call_bedrock(internal_tier, context)
    questions = _normalise_questions(internal_tier, payload)
    topics_joined = context.joined_topics()
    topics_count = len([item for item in topics_joined.split(",") if item.strip()])
    return {
        "topic_context": {
            "topic_id": context.topic_id,
            "topic_title": context.topic_title,
            "module_code": context.module_code,
            "topics_list": topics_joined,
            "topic_ids_used": context.topic_ids_used,
            "topic_titles_used": context.topic_titles_used,
            "topic_window": context.week_window_label(),
            "topic_history": context.history_summary(),
            "topics_count": topics_count,
            "topic_history_items": context.topic_history,
        },
        "challenge_data": {
            "challenge_set_title": payload.get("challenge_set_title"),
            "questions": questions,
        },
    }



async def generate_and_save_tier(
    tier: str,
    week: int,
    slide_stack_id: Optional[int] = None,
    module_code: Optional[str] = None,
    lecturer_id: Optional[int] = None,
) -> Dict[str, Any]:
    internal_tier = _tier_from_kind(tier)
    context = await _fetch_topic_context(week, slide_stack_id=slide_stack_id, module_code=module_code, tier=internal_tier)
    client = await get_supabase()
    if lecturer_id is None:
        raise ValueError("lecturer_id is required to persist generated challenges")
    payload = await _call_bedrock(internal_tier, context)
    questions = _normalise_questions(internal_tier, payload)
    challenge = await _insert_challenge(
        client,
        tier=internal_tier,
        context=context,
        challenge_title=payload.get("challenge_set_title") or f"Week {week} {internal_tier.title()} Challenge",
        challenge_description=f"Auto-generated {internal_tier} challenge for Week {week} covering {context.topic_title}.",
        lecturer_id=lecturer_id,
    )
    stored = []
    existing_q = await client.table("questions").select("id").eq("challenge_id", challenge.get("id")).execute()
    existing_ids = [str(r.get("id")) for r in (existing_q.data or []) if r.get("id")]
    if existing_ids:
        stored = [{"id": qid} for qid in existing_ids]
    else:
        for idx, question in enumerate(questions, start=1):
            stored.append(
                await _insert_question(
                    client,
                    challenge_id=challenge.get("id"),
                    question=question,
                    order_index=idx,
                )
            )
    topics_joined = context.joined_topics()
    topics_count = len([item for item in topics_joined.split(",") if item.strip()])
    return {
        "topic_context": {
            "topic_id": context.topic_id,
            "topic_title": context.topic_title,
            "module_code": context.module_code,
            "topics_list": topics_joined,
            "topic_ids_used": context.topic_ids_used,
            "topic_titles_used": context.topic_titles_used,
            "topic_window": context.week_window_label(),
            "topic_history": context.history_summary(),
            "topics_count": topics_count,
            "topic_history_items": context.topic_history,
        },
        "challenge": challenge,
        "questions": stored,
        "tier": internal_tier,
    }



async def fetch_topic_context_summary(
    week: int,
    slide_stack_id: Optional[int] = None,
    module_code: Optional[str] = None,
    tier: str = "base",
) -> Dict[str, Any]:
    context = await _fetch_topic_context(week, slide_stack_id=slide_stack_id, module_code=module_code, tier=tier)
    return {
        "topic_id": context.topic_id,
        "topic_title": context.topic_title,
        "module_code": context.module_code,
        "topics_list": context.joined_topics(),
        "topic_ids_used": context.topic_ids_used,
        "topic_titles_used": context.topic_titles_used,
    }

