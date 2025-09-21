from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.DB.supabase import get_supabase
from app.features.challenges.ai.bedrock_client import invoke_claude

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


@dataclass
class TopicContext:
    week: int
    module_code: Optional[str]
    topic_id: Optional[str]
    topic_title: str
    topic_slug: Optional[str]
    prompt_topics: List[str]

    def joined_topics(self) -> str:
        items = [t.strip() for t in self.prompt_topics if t and str(t).strip()]
        if not items:
            items = DEFAULT_TOPICS
        return ", ".join(dict.fromkeys(items))


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


async def _fetch_topic_context(
    week: int,
    slide_stack_id: Optional[int] = None,
    module_code: Optional[str] = None,
) -> TopicContext:
    client = await get_supabase()
    topic_id: Optional[str] = None
    prompt_topics: List[str] = []
    topic_title = f"Week {week} Topic"
    topic_slug: Optional[str] = None

    if slide_stack_id is not None:
        resp = await client.table("slide_extractions").select(
            "id, topic_id, detected_topic, detected_subtopics, module_code, week_number"
        ).eq("id", slide_stack_id).limit(1).execute()
        rows = resp.data or []
        if rows:
            row = rows[0]
            topic_id = row.get("topic_id") or topic_id
            module_code = module_code or row.get("module_code")
            prompt_topics.extend(_ensure_list(row.get("detected_subtopics")))
            if row.get("detected_topic"):
                prompt_topics.append(str(row["detected_topic"]))

    topic_row: Optional[Dict[str, Any]] = None
    if topic_id:
        t_resp = await client.table("topic").select(
            "id, title, slug, detected_topic, detected_subtopics, subtopics, module_code_slidesdeck"
        ).eq("id", topic_id).limit(1).execute()
        t_rows = t_resp.data or []
        if t_rows:
            topic_row = t_rows[0]
    if topic_row is None:
        query = client.table("topic").select(
            "id, title, slug, detected_topic, detected_subtopics, subtopics, module_code_slidesdeck"
        ).eq("week", week)
        if module_code:
            query = query.eq("module_code_slidesdeck", module_code)
        try:
            query = query.order("created_at", desc=True)
        except Exception:
            try:
                query = query.order("id", desc=True)
            except Exception:
                pass
        t_resp = await query.limit(1).execute()
        t_rows = t_resp.data or []
        if t_rows:
            topic_row = t_rows[0]
            topic_id = topic_row.get("id")
            if not module_code:
                module_code = topic_row.get("module_code_slidesdeck")

    if topic_row:
        title = topic_row.get("title") or topic_row.get("slug")
        if title:
            topic_title = str(title)
        topic_slug = topic_row.get("slug")
        prompt_topics.extend(_ensure_list(topic_row.get("subtopics")))
        prompt_topics.extend(_ensure_list(topic_row.get("detected_subtopics")))
        if topic_row.get("detected_topic"):
            prompt_topics.append(str(topic_row["detected_topic"]))

    context = TopicContext(
        week=week,
        module_code=module_code,
        topic_id=str(topic_id) if topic_id else None,
        topic_title=topic_title,
        topic_slug=topic_slug,
        prompt_topics=prompt_topics or DEFAULT_TOPICS,
    )
    return context


def _load_template(kind: str) -> str:
    base_dir = Path(__file__).parent.parent / "prompts"
    templates = {
        "common": "base.txt",
        "base": "base.txt",
        "ruby": "ruby.txt",
        "emerald": "emerald.txt",
        "diamond": "diamond.txt",
    }
    name = templates.get(kind, "base.txt")
    path = base_dir / name
    return path.read_text(encoding="utf-8")


def _render_prompt(template: str, context: TopicContext) -> str:
    prompt = template
    prompt = prompt.replace("{{week_number}}", str(context.week))
    prompt = prompt.replace("{{topic_title}}", context.topic_title)
    prompt = prompt.replace("{{topics_list}}", context.joined_topics())
    return prompt


def _normalise_question(kind: str, question: Dict[str, Any], expected_difficulty: Optional[str]) -> Dict[str, Any]:
    difficulty = str(question.get("difficulty_level", "")).title()
    if expected_difficulty:
        difficulty = expected_difficulty
    elif kind in {"ruby", "emerald", "diamond"}:
        difficulty = kind.title()
    question["difficulty_level"] = difficulty

    starter_code = question.get("starter_code") or ""
    reference_solution = question.get("reference_solution") or ""
    question["starter_code"] = str(starter_code)
    question["reference_solution"] = str(reference_solution)

    tests = question.get("tests") or []
    normalised_tests: List[Dict[str, str]] = []
    for index, test in enumerate(tests):
        if not isinstance(test, dict):
            continue
        visibility = str(test.get("visibility", "public" if index == 0 else "private")).lower()
        if visibility not in {"public", "private"}:
            visibility = "public" if index == 0 else "private"
        normalised_tests.append(
            {
                "input": str(test.get("input", "")),
                "expected": str(test.get("expected", "")),
                "visibility": visibility,
            }
        )
    if not normalised_tests:
        normalised_tests = [{"input": "", "expected": "", "visibility": "public"}]
    question["tests"] = normalised_tests
    return question


def _normalise_questions(kind: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    questions = payload.get("questions", [])
    if kind in {"common", "base"}:
        if len(questions) < 5:
            raise ValueError("Claude response did not include 5 questions for base/common payload")
        selected = questions[:5]
        return [
            _normalise_question(kind, selected[i], BASE_DISTRIBUTION[i])
            for i in range(5)
        ]
    if not questions:
        raise ValueError(f"Claude response did not include questions for tier {kind}")
    return [_normalise_question(kind, questions[0], kind.title())]


async def _call_bedrock(kind: str, context: TopicContext) -> Dict[str, Any]:
    template = _load_template(kind)
    prompt = _render_prompt(template, context)
    return await invoke_claude(prompt)


async def _insert_challenge(
    client,
    *,
    tier: str,
    context: TopicContext,
    challenge_title: str,
    challenge_description: str,
) -> Dict[str, Any]:
    slug_origin = context.topic_slug or challenge_title or challenge_description
    slug_base = _slugify(slug_origin)
    module_part = _slugify(context.module_code or "module")
    slug = f"{module_part}-w{context.week:02d}-{tier}"
    payload = {
        "title": challenge_title,
        "description": challenge_description,
        "slug": slug,
        "status": "draft",
        "tier": tier,
        "kind": tier,
        "topic_id": context.topic_id,
        "week_number": context.week,
        "linked_module": context.module_code,
    }
    resp = await client.table("challenges").insert(payload).execute()
    if not resp.data:
        raise ValueError(f"Failed to create challenge for tier {tier}")
    return resp.data[0]


async def _insert_tests(client, question_id: Any, tests: List[Dict[str, str]]) -> None:
    for test in tests:
        payload = {
            "question_id": question_id,
            "input": test.get("input", ""),
            "expected": test.get("expected", ""),
            "visibility": test.get("visibility", "public"),
        }
        await client.table("tests").insert(payload).execute()


async def _insert_question(
    client,
    *,
    challenge_id: Any,
    question: Dict[str, Any],
    order_index: int,
) -> Dict[str, Any]:
    difficulty = question.get("difficulty_level", "Bronze")
    points = POINTS_BY_DIFFICULTY.get(difficulty, 10)
    tests = question.get("tests", [])
    public_expected = next((t.get("expected") for t in tests if t.get("visibility") == "public"), None)
    if public_expected is None and tests:
        public_expected = tests[0].get("expected")
    payload = {
        "challenge_id": challenge_id,
        "language_id": 71,
        "expected_output": public_expected,
        "points": points,
        "starter_code": question.get("starter_code", ""),
        "max_time_ms": 2000,
        "max_memory_kb": 256000,
        "tier": difficulty.lower(),
        "question_text": question.get("question_text"),
        "reference_solution": question.get("reference_solution"),
        "question_number": order_index,
    }
    resp = await client.table("questions").insert(payload).execute()
    if not resp.data:
        raise ValueError("Failed to insert question")
    record = resp.data[0]
    await _insert_tests(client, record.get("id"), tests)
    return record


class ClaudeChallengeGenerator:
    def __init__(self, week: int, slide_stack_id: Optional[int] = None, module_code: Optional[str] = None):
        self.week = week
        self.slide_stack_id = slide_stack_id
        self.module_code = module_code
        self._client = None

    async def _client_handle(self):
        if self._client is None:
            self._client = await get_supabase()
        return self._client

    async def generate(self) -> Dict[str, Any]:
        context = await _fetch_topic_context(
            self.week,
            slide_stack_id=self.slide_stack_id,
            module_code=self.module_code,
        )
        client = await self._client_handle()

        created: Dict[str, Optional[Dict[str, Any]]] = {"base": None, "ruby": None, "emerald": None, "diamond": None}
        topics_used = context.joined_topics()

        async def _generate_and_store(tier: str) -> Optional[Dict[str, Any]]:
            try:
                payload = await _call_bedrock(tier, context)
                questions = _normalise_questions(tier, payload)
                challenge = await _insert_challenge(
                    client,
                    tier=tier,
                    context=context,
                    challenge_title=payload.get("challenge_set_title") or f"Week {self.week} {tier.title()} Challenge",
                    challenge_description=f"Auto-generated {tier} challenge for Week {self.week} covering {context.topic_title}.",
                )
                stored_questions = []
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
                }
            except Exception as exc:
                print(f"[claude-generator] Skipped {tier}: {exc}")
                return None

        created["base"] = await _generate_and_store("base")
        created["ruby"] = await _generate_and_store("ruby")
        created["emerald"] = await _generate_and_store("emerald")
        created["diamond"] = await _generate_and_store("diamond")

        return {
            "week": self.week,
            "topics_used": topics_used,
            "topic_id": context.topic_id,
            "module_code": context.module_code,
            "created": created,
            "status": "completed",
        }


def _tier_from_kind(tier: str) -> str:
    return "base" if tier == "common" else tier


async def generate_challenges_with_claude(
    week: int,
    slide_stack_id: Optional[int] = None,
    module_code: Optional[str] = None,
) -> Dict[str, Any]:
    generator = ClaudeChallengeGenerator(week, slide_stack_id=slide_stack_id, module_code=module_code)
    return await generator.generate()


async def generate_tier_preview(
    tier: str,
    week: int,
    slide_stack_id: Optional[int] = None,
    module_code: Optional[str] = None,
) -> Dict[str, Any]:
    internal_tier = _tier_from_kind(tier)
    context = await _fetch_topic_context(week, slide_stack_id=slide_stack_id, module_code=module_code)
    payload = await _call_bedrock(internal_tier, context)
    questions = _normalise_questions(internal_tier, payload)
    return {
        "topic_context": {
            "topic_id": context.topic_id,
            "topic_title": context.topic_title,
            "module_code": context.module_code,
            "topics_list": context.joined_topics(),
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
) -> Dict[str, Any]:
    internal_tier = _tier_from_kind(tier)
    context = await _fetch_topic_context(week, slide_stack_id=slide_stack_id, module_code=module_code)
    client = await get_supabase()
    payload = await _call_bedrock(internal_tier, context)
    questions = _normalise_questions(internal_tier, payload)
    challenge = await _insert_challenge(
        client,
        tier=internal_tier,
        context=context,
        challenge_title=payload.get("challenge_set_title") or f"Week {week} {internal_tier.title()} Challenge",
        challenge_description=f"Auto-generated {internal_tier} challenge for Week {week} covering {context.topic_title}.",
    )
    stored = []
    for idx, question in enumerate(questions, start=1):
        stored.append(
            await _insert_question(
                client,
                challenge_id=challenge.get("id"),
                question=question,
                order_index=idx,
            )
        )
    return {
        "topic_context": {
            "topic_id": context.topic_id,
            "topic_title": context.topic_title,
            "module_code": context.module_code,
            "topics_list": context.joined_topics(),
        },
        "challenge": challenge,
        "questions": stored,
        "tier": internal_tier,
    }


async def fetch_topic_context_summary(
    week: int,
    slide_stack_id: Optional[int] = None,
    module_code: Optional[str] = None,
) -> Dict[str, Any]:
    context = await _fetch_topic_context(week, slide_stack_id=slide_stack_id, module_code=module_code)
    return {
        "topic_id": context.topic_id,
        "topic_title": context.topic_title,
        "module_code": context.module_code,
        "topics_list": context.joined_topics(),
    }
