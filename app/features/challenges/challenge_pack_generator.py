from __future__ import annotations

import os

from app.features.challenges.tier_utils import BASE_TIER, normalise_challenge_tier
import asyncio
import hashlib
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    from jsonschema import validate as _jsonschema_validate, ValidationError as _JsonSchemaValidationError
    ValidationError = _JsonSchemaValidationError
    def validate(instance, schema):
        return _jsonschema_validate(instance, schema)
except Exception:
    class ValidationError(Exception):
        pass
    def validate(instance, schema):
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
    "Gold": 40,
    "Ruby": 80,
    "Emerald": 120,
    "Diamond": 200,
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
            if start:
                return f"Week {start}"
            if end:
                return f"Week {end}"
        if self.week:
            return f"Week {self.week}"
        return "Week"

TOPIC_LIMIT_BY_TIER = {
    BASE_TIER: 1,
    "ruby": 2,
    "emerald": 4,
    "diamond": 12,
}


def _tier_from_kind(kind: Optional[str]) -> str:
    """Normalize a requested tier/kind to the internal tier key.

    Accepts values like 'base', 'ruby', 'emerald', 'diamond' and
    returns the canonical lowercase key used across this module.
    """
    normalised = normalise_challenge_tier(kind)
    if normalised:
        return normalised
    if kind is None:
        return BASE_TIER
    return str(kind).strip().lower()


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
        except Exception:
            return [value]
    return []


TOPIC_WINDOW_BY_TIER = {
    BASE_TIER: 1,
    "ruby": 2,
    "emerald": 4,
    "diamond": None,
}

def _slugify(value: str) -> str:
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return slug or "challenge"


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
    # Use per-tier window sizes. TOPIC_WINDOW_BY_TIER contains the configured sliding window
    # for each tier (ruby=2, emerald=4, diamond=None meaning full history up to the requested week).
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

    # If window_weeks is None, _collect_topic_rows will not filter by a sliding window and we will
    # fetch rows up to `week` (i.e., weeks <= requested week) allowing special tiers to use topics
    # from week 1..week.
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
        BASE_TIER: "base.txt",
        "ruby": "ruby.txt",
        "emerald": "emerald.txt",
        "diamond": "diamond.txt",
    }
    canonical_kind = normalise_challenge_tier(kind) or str(kind).strip().lower()
    name = templates.get(canonical_kind, "base.txt")
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
    return prompt


async def generate_tier_preview(
    tier: str,
    week: int,
    slide_stack_id: Optional[int] = None,
    module_code: Optional[str] = None,
) -> Dict[str, Any]:
    internal_tier = _tier_from_kind(tier)
    context = await _fetch_topic_context(week, slide_stack_id=slide_stack_id, module_code=module_code, tier=internal_tier)
    payload = await _call_bedrock(internal_tier, context)
    try:
        questions = _normalise_questions(internal_tier, payload)
    except Exception:
        # Fail quietly — caller handles optional tier failures
        raise
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


def _normalise_questions(kind: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        logger.warning("Generator payload is not a dict for tier %s: %r", kind, payload)
        raise ValueError("Model response invalid: expected object payload")
    questions = payload.get("questions", []) or []
    if normalise_challenge_tier(kind) == BASE_TIER:
        if len(questions) < 5:
            raise ValueError("Model response did not include 5 questions for base payload")
        selected = questions[:5]
        return [
            _normalise_question(kind, selected[i], BASE_DISTRIBUTION[i])
            for i in range(5)
        ]
    if not questions:
        raise ValueError(f"Model response did not include questions for tier {kind}")
    # ensure the first question is a dict
    first = questions[0]
    if not isinstance(first, dict):
        logger.warning("First question is not a dict for tier %s: %r", kind, first)
        raise ValueError("Model response invalid: question item not an object")
    return [_normalise_question(kind, first, kind.title())]


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
            continue

def _normalise_question(kind: str, data: Dict[str, Any], difficulty: str) -> Dict[str, Any]:
            """Minimal normalisation of a single question payload for downstream code paths.
            Conservative: extracts title, starter code and normalises testcases to a list of at least
            3 items with visibility flags. Defensive against None/malformed question objects.
            """
            if not isinstance(data, dict):
                logger.warning("Normalise called with non-dict question data: %r", data)
                data = {}
            title = (data.get("title") or (data.get("question_text") or "")).split("\n")[0][:120]
            tests = data.get("tests") or data.get("testcases") or []
            normalised_tests = []
            for test in tests:
                if not isinstance(test, dict):
                    logger.warning("Skipping non-dict testcase for question '%s': %r", title, test)
                    continue
                visibility = test.get("visibility") or ("public" if not normalised_tests else "private")
                normalised_tests.append({
                    "input": str(test.get("input") or test.get("stdin") or ""),
                    "expected": str(test.get("expected") or test.get("expected_output") or ""),
                    "visibility": visibility,
                })
            while len(normalised_tests) < 3:
                visibility = "public" if not normalised_tests else "private"
                normalised_tests.append({"input": "", "expected": "", "visibility": visibility})
            difficulty_key = difficulty.title() if isinstance(difficulty, str) else str(difficulty)
            points_value = POINTS_BY_DIFFICULTY.get(difficulty_key)
            if points_value is None:
                points_value = POINTS_BY_DIFFICULTY.get(str(difficulty).capitalize(), 10)
            result = {
                "title": title,
                "question_text": data.get("question_text") or data.get("prompt") or "",
                "difficulty_level": difficulty,
                "starter_code": data.get("starter_code") or "",
                "reference_solution": data.get("reference_solution") or "",
                "tests": normalised_tests,
                "points": int(points_value),
                "tier": str(difficulty).lower(),
            }

            return result

async def _insert_challenge(
    client,
    *,
    tier: str,
    context: TopicContext,
    challenge_title: str,
    challenge_description: str,
    lecturer_id: Optional[int],
    week_number: Optional[int],
    semester_id: Optional[str] = None,
) -> Dict[str, Any]:
    if lecturer_id is None:
        raise ValueError("lecturer_id is required to insert challenge")

    module_part = _slugify(context.module_code or "module")
    requested_week = week_number if week_number is not None else context.week
    try:
        effective_week = int(requested_week) if requested_week is not None else 0
    except (TypeError, ValueError):
        effective_week = 0
    if effective_week <= 0:
        try:
            effective_week = int(context.week) if context.week is not None else 0
        except Exception:
            effective_week = 0
    if effective_week <= 0:
        effective_week = 1
    effective_week = max(1, min(12, effective_week))

    slug_week = 12 if tier == "diamond" else effective_week
    tier_slug = "base" if normalise_challenge_tier(tier) == BASE_TIER else _slugify(tier)
    slug = f"{module_part}-w{int(slug_week):02d}-{tier_slug}"
    is_weekly = tier == "base"
    challenge_type_value = "weekly" if is_weekly else "special"
    tier_value = None if is_weekly else (BASE_TIER if normalise_challenge_tier(tier) == BASE_TIER else tier)

    key_source = "|".join([
        str(context.topic_id or ""),
        str(context.module_code or ""),
        str(slug_week),
        tier,
    ])
    idempotency_key = hashlib.sha256(key_source.encode("utf-8")).hexdigest()[:16]

    async def _fetch_existing(field: str, value: Any) -> Optional[Dict[str, Any]]:
        """Query the challenges table for a single row matching field==value.
        Returns a dict row or None. Handles missing column and DB errors gracefully.
        """
        if value in {None, ""}:
            return None
        try:
            # Defensive: check if column exists (some deployments may not have new columns)
            has_col = await _table_has_column("challenges", field)
        except Exception:
            has_col = False
        try:
            # If column doesn't exist, still attempt a safe query; Supabase will error if invalid
            rows = await client.table("challenges").select("*").eq(field, value).limit(1).execute()
            if getattr(rows, "data", None):
                return rows.data[0]
            return None
        except Exception:
            return None

    async def _table_has_column(table: str, column: str) -> bool:
        try:
            await client.table(table).select(column).limit(1).execute()
            return True
        except Exception:
            return False

    supports_idempotency = await _table_has_column("challenges", "idempotency_key")
    # Detect if the challenges table supports a semester_id column so we can scope existence checks
    try:
        supports_semester = await _table_has_column("challenges", "semester_id")
    except Exception:
        supports_semester = False
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
        existing = await _fetch_existing("slug", slug)
    if existing:
        try:
            if isinstance(existing, dict):
                existing.setdefault("idempotency_key", idempotency_key)
                existing.setdefault("_existing", True)
        except Exception:
            pass
        return existing

    payload = {
        "title": challenge_title,
        "description": challenge_description,
        "status": "draft",
    }

    if context.module_code:
        payload.setdefault("module_code", context.module_code)

    payload["challenge_type"] = challenge_type_value
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    payload["release_date"] = now.isoformat()
    payload["due_date"] = (now + timedelta(days=7)).isoformat()

    if is_weekly:
        payload["week_number"] = effective_week
        # Do not explicitly set the `tier` enum for weekly challenges. Different
        # deployments may use different legacy enum members; leave relaxed matching in place
        # the column unset so DB defaults or downstream logic can normalise it.
        pass
    else:
        # Do not set the `tier` enum value explicitly; deployments may use different
        # enum labels. Keep week number and trigger_event metadata but leave tier
        # unset so DB defaults or downstream logic can normalise it as needed.
        if tier == "diamond":
            payload["week_number"] = 12
        else:
            payload["week_number"] = effective_week
            payload["trigger_event"] = {"auto_generated": True, "week": effective_week}

    if semester_id:
        try:
            if await _table_has_column("challenges", "semester_id"):
                payload["semester_id"] = semester_id
        except Exception:
            pass

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
        logger.debug("challenge payload prepared (not yet inserted): %s", payload)
    except Exception:
        pass
    try:
        if await _table_has_column("challenges", "lecturer_creator") and lecturer_id is not None:
            payload["lecturer_creator"] = int(lecturer_id)
    except Exception:
        pass
    if supports_idempotency:
        payload["idempotency_key"] = idempotency_key

    module_code_filter = context.module_code
    try:
        if is_weekly:
            try:
                query = client.table("challenges").select("id").eq("challenge_type", "weekly").eq("week_number", effective_week)
                if module_code_filter:
                    query = query.eq("module_code", module_code_filter)
                if supports_semester and semester_id:
                    query = query.eq("semester_id", semester_id)
                exists_resp = await query.limit(1).execute()
                if getattr(exists_resp, "data", None):
                    raise RuntimeError(f"A weekly challenge already exists for week {effective_week}")
            except Exception:
                pass
        else:
            found = None
            try:
                query = client.table("challenges").select("id").eq("challenge_type", "special").eq("week_number", effective_week)
                if module_code_filter:
                    query = query.eq("module_code", module_code_filter)
                if supports_semester and semester_id:
                    query = query.eq("semester_id", semester_id)
                exists_resp = await query.limit(1).execute()
                if getattr(exists_resp, "data", None):
                    found = True
            except Exception:
                found = None
            if not found:
                try:
                    query = client.table("challenges").select("id").eq("challenge_type", "special")
                    if module_code_filter:
                        query = query.eq("module_code", module_code_filter)
                    if supports_semester and semester_id:
                        query = query.eq("semester_id", semester_id)
                    trigger_resp = await query.eq("trigger_event->>week", str(effective_week)).limit(1).execute()
                    if getattr(trigger_resp, "data", None):
                        found = True
                except Exception:
                    found = None
            if found:
                raise RuntimeError(f"A special challenge already exists for week {effective_week}")
    except RuntimeError:
        raise
    except Exception:
        pass

    resp = await client.table("challenges").insert(payload).execute()
    if not resp.data:
        raise ValueError(f"Failed to create challenge for tier {tier}")
    record = resp.data[0]
    try:
        if isinstance(record, dict):
            record.setdefault("_existing", False)
    except Exception:
        pass
    # After creating an active challenge, prune older active challenges so we never
    # keep more than the configured number of active challenges (default: 2)
    # per module_code + semester_id scope. This calls a Postgres RPC function
    # `prune_active_challenges(challenge_id uuid, keep_count int)` which should be
    # created in the Supabase database. Failures here should not block insertion.
    try:
        # Try best-effort RPC call; some deployments may not have the function yet.
        await client.rpc("prune_active_challenges", {"challenge_id": record.get("id"), "keep_count": 2}).execute()
    except Exception:
        pass
    return record

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
    semester_id: Optional[str] = None,
) -> Dict[str, Any]:
    internal_tier = _tier_from_kind(tier)
    context = await _fetch_topic_context(week, slide_stack_id=slide_stack_id, module_code=module_code, tier=internal_tier)
    try:
        week_int = int(week)
    except (TypeError, ValueError):
        week_int = 0
    if week_int <= 0:
        try:
            week_int = int(context.week) if context.week is not None else 0
        except Exception:
            week_int = 0
    if week_int <= 0:
        week_int = 1
    display_week = week_int
    client = await get_supabase()
    if lecturer_id is None:
        raise ValueError("lecturer_id is required to persist generated challenges")
    payload = await _call_bedrock(internal_tier, context)
    questions = _normalise_questions(internal_tier, payload)
    challenge = await _insert_challenge(
        client,
        tier=internal_tier,
        context=context,
        challenge_title=payload.get("challenge_set_title") or f"Week {display_week} {internal_tier.title()} Challenge",
        challenge_description=f"Auto-generated {internal_tier} challenge for Week {display_week} covering {context.topic_title}.",
        lecturer_id=lecturer_id,
        week_number=week_int,
        semester_id=semester_id,
    )
    # Link the newly created challenge to detected topics via challenge_topics
    try:
        topic_ids = context.topic_ids_used or []
        for tid in topic_ids:
            try:
                await client.table("challenge_topics").insert({
                    "challenge_id": challenge.get("id"),
                    "topic_id": tid,
                }).execute()
            except Exception:
                pass
    except Exception:
        pass
    stored = []
    existing_q = await client.table("questions").select("id").eq("challenge_id", challenge.get("id")).execute()
    existing_ids = [str(r.get("id")) for r in (existing_q.data or []) if r.get("id")]
    if existing_ids:
        stored = [{"id": qid} for qid in existing_ids]
    else:
        
        async def _insert_question(client, *, challenge_id: Any, question: Dict[str, Any], order_index: int) -> Dict[str, Any]:
            """Insert a question row into the questions table defensively, persist its testcases,
            and return the inserted record (or a minimal fallback). Log any DB errors so failures
            are visible in server logs.
            """
            # Align inserted fields with the actual `questions` table schema
            # Use question_number/sub_number and provide minimal required fields (points > 0)
            payload_q = {
                "challenge_id": challenge_id,
                "question_number": int(order_index),
                "sub_number": 0,
                "title": question.get("title"),
                "question_text": question.get("question_text") or question.get("prompt") or "",
                "reference_solution": question.get("reference_solution") or "",
                "starter_code": question.get("starter_code") or "",
                "points": int(question.get("points") or 1),
                # language_id default exists in DB (71) but set explicitly when available
                "language_id": int(question.get("language_id") or 71),
                "expected_output": str((question.get("reference_solution") or question.get("expected") or question.get("expected_output") or "")),
                "tier": question.get("difficulty_level") or None,
            }
            # Attempt to insert the question row with a single retry on transient failures.
            import os as _os
            _debug = _os.environ.get("GENERATOR_DEBUG") in {"1", "true", "True"}
            q_attempt = 0
            while q_attempt < 2:
                try:
                    resp_q = await client.table("questions").insert(payload_q).execute()
                    try:
                        logger.debug("questions.insert response: data=%r error=%r", getattr(resp_q, 'data', None), getattr(resp_q, 'error', None))
                    except Exception:
                        pass
                    inserted = getattr(resp_q, "data", None)
                    if inserted:
                        qrow = inserted[0]
                        qid = qrow.get("id")
                        # Persist testcases into question_tests (preferred) or legacy tests table
                        tests = question.get("tests") or []
                        persisted_count = 0
                        persisted_rows: List[Dict[str, Any]] = []
                        if tests and qid is not None:
                            # Detect once which expected column variant the table supports.
                            has_expected_output: Optional[bool] = None

                            async def _supports_expected_output() -> bool:
                                nonlocal has_expected_output
                                if has_expected_output is not None:
                                    return has_expected_output
                                try:
                                    await client.table("question_tests").select("id,expected_output").limit(1).execute()
                                    has_expected_output = True
                                except Exception:
                                    has_expected_output = False
                                return has_expected_output

                            for t in tests:
                                expected_val = str(t.get("expected") or t.get("expected_output") or "")
                                visibility_val = t.get("visibility") or None
                                if isinstance(visibility_val, str) and visibility_val.strip().lower() == "private":
                                    visibility_val = "hidden"
                                base_input = str(t.get("input") or "")

                                async def _insert_testcase() -> bool:
                                    """Try inserting a testcase handling schema variants (expected vs expected_output).
                                    Returns True if persisted, False otherwise."""
                                    use_expected_output = await _supports_expected_output()
                                    payload_primary = {
                                        "question_id": qid,
                                        "input": base_input,
                                        ("expected_output" if use_expected_output else "expected"): expected_val,
                                        "visibility": visibility_val,
                                    }
                                    try:
                                        resp_t = await client.table("question_tests").insert(payload_primary).execute()
                                        if getattr(resp_t, "data", None):
                                            try:
                                                persisted_rows.append(resp_t.data[0])
                                            except Exception:
                                                persisted_rows.append({"question_id": qid})
                                            return True
                                    except Exception as _pri_exc:
                                        if _debug:
                                            try:
                                                logger.debug("Primary insert failed (column %s) for qid=%s: %s", 'expected_output' if use_expected_output else 'expected', qid, _pri_exc)
                                            except Exception:
                                                pass
                                        # If we assumed wrong, flip and retry once
                                        if use_expected_output is True:
                                            try:
                                                resp_t2 = await client.table("question_tests").insert({
                                                    "question_id": qid,
                                                    "input": base_input,
                                                    "expected": expected_val,
                                                    "visibility": visibility_val,
                                                }).execute()
                                                if getattr(resp_t2, "data", None):
                                                    has_expected_output = False  # cache for subsequent iterations
                                                    try:
                                                        persisted_rows.append(resp_t2.data[0])
                                                    except Exception:
                                                        persisted_rows.append({"question_id": qid})
                                                    return True
                                            except Exception as _sec_exc:
                                                if _debug:
                                                    try:
                                                        logger.debug("Secondary insert failed (expected) for qid=%s: %s", qid, _sec_exc)
                                                    except Exception:
                                                        pass
                                        else:
                                            # we tried 'expected' first; attempt 'expected_output'
                                            try:
                                                resp_t3 = await client.table("question_tests").insert({
                                                    "question_id": qid,
                                                    "input": base_input,
                                                    "expected_output": expected_val,
                                                    "visibility": visibility_val,
                                                }).execute()
                                                if getattr(resp_t3, "data", None):
                                                    has_expected_output = True
                                                    try:
                                                        persisted_rows.append(resp_t3.data[0])
                                                    except Exception:
                                                        persisted_rows.append({"question_id": qid})
                                                    return True
                                            except Exception as _ter_exc:
                                                if _debug:
                                                    try:
                                                        logger.debug("Tertiary insert failed (expected_output) for qid=%s: %s", qid, _ter_exc)
                                                    except Exception:
                                                        pass
                                    return False

                                success = False
                                for t_attempt in range(2):
                                    if await _insert_testcase():
                                        persisted_count += 1
                                        success = True
                                        break
                                if not success:
                                    # Final failure inserting into question_tests; try legacy `tests` table as a fallback
                                    try:
                                        legacy_payload = {
                                            "question_id": qid,
                                            "input": base_input,
                                            "expected": expected_val,
                                            "visibility": visibility_val,
                                        }
                                        try:
                                            resp_leg = await client.table("tests").insert(legacy_payload).execute()
                                            if getattr(resp_leg, "data", None):
                                                try:
                                                    persisted_rows.append(resp_leg.data[0])
                                                except Exception:
                                                    persisted_rows.append({"question_id": qid})
                                                persisted_count += 1
                                                if _debug:
                                                    try:
                                                        logger.debug("Inserted testcase into legacy tests table for qid=%s", qid)
                                                    except Exception:
                                                        pass
                                        except Exception as _leg_exc:
                                            if _debug:
                                                try:
                                                    logger.debug("Failed legacy tests insert for qid=%s: %s", qid, _leg_exc)
                                                except Exception:
                                                    pass
                                    except Exception:
                                        pass
                        # attach diag info for caller: actual persisted count and rows
                        try:
                            qrow.setdefault("_persisted_tests", persisted_count)
                            if persisted_rows:
                                qrow.setdefault("testcases", persisted_rows)
                        except Exception:
                            pass
                        return qrow
                    # else fallthrough to retry
                except Exception as _q_exc:
                    q_attempt += 1
                    if _debug:
                        try:
                            logger.exception("Failed to insert question (attempt %s) for challenge=%s index=%s: %s", q_attempt, challenge_id, order_index, _q_exc)
                        except Exception:
                            pass
                    if q_attempt >= 2:
                        break
            # Fallback: return a minimal representation and include an error note
            return {"id": None, "challenge_id": challenge_id, "question_number": order_index, "sub_number": 0, "_error": "persist_failed"}

        for idx, question in enumerate(questions, start=1):
            stored.append(await _insert_question(client, challenge_id=challenge.get("id"), question=question, order_index=idx))
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

