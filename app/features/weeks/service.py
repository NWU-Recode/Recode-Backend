"""Weeks orchestration service (MVP).

Generates Topic + Challenges + Questions from slides metadata and templates,
persists to Supabase, and validates reference solutions via Judge0.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional, Tuple
import re

from app.DB.supabase import get_supabase
from app.features.topics.service import TopicService
from app.features.topic_detections.repository import question_repository
from app.adapters.judge0_client import run_many
from app.features.topic_detections.templates.strings import template_reverse_string
from app.features.challenges.ai.generator import generate_question_spec


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


class WeeksOrchestrator:
    def __init__(self, week: int, slides_url: str, force: bool = False):
        self.week = week
        self.slides_url = slides_url
        self.force = force

    async def _ensure_topic(self) -> Dict[str, Any]:
        # If slides_url points to Supabase storage, try fetching and extracting text
        slide_texts: Optional[List[str]] = None
        try:
            if isinstance(self.slides_url, str) and self.slides_url.startswith("supabase://"):
                # Format: supabase://<bucket>/<object_key>
                _, _, rest = self.slides_url.partition("supabase://")
                bucket, _, object_key = rest.partition("/")
                if bucket and object_key:
                    client = await get_supabase()
                    downloader = client.storage.from_(bucket).download(object_key)
                    data = await downloader if hasattr(downloader, "__await__") else downloader
                    if isinstance(data, dict) and "data" in data:
                        data = data["data"]
                    if isinstance(data, (bytes, bytearray)):
                        from io import BytesIO
                        from app.features.questions.slide_extraction.pptx_extraction import extract_pptx_text
                        try:
                            slides_map = extract_pptx_text(BytesIO(data))
                            # Flatten to list of strings for NLP
                            slide_texts = [line for _, lines in sorted(slides_map.items()) for line in lines]
                        except Exception:
                            slide_texts = None
        except Exception:
            slide_texts = None
        return await TopicService.create_from_slides(self.slides_url, self.week, slide_texts=slide_texts)

    async def _create_challenge(self, kind: str, topic: Dict[str, Any]) -> Dict[str, Any]:
        client = await get_supabase()
        topic_slug = topic.get("slug", f"w{self.week:02d}-topic")
        if kind == "common":
            slug = f"{topic_slug}-common"
            title = f"Week {self.week} – {topic.get('title', 'Topic')} (Common)"
        elif kind == "ruby":
            slug = f"w{self.week:02d}-ruby"
            title = f"Week {self.week} – Ruby"
        elif kind == "platinum":
            slug = f"w{self.week:02d}-platinum"
            title = f"Week {self.week} – Platinum"
        elif kind == "diamond":
            slug = "diamond-final"
            title = "Diamond – Final Capstone"
        else:
            slug = f"w{self.week:02d}-{kind}"
            title = f"Week {self.week} – {kind.title()}"

        # See available columns from Supabase; keep to safe columns
        payload = {
            "title": title,
            "description": f"Auto-generated challenge ({kind}) for {topic.get('title','Topic')}.",
            # Best-effort extras (ignored if columns absent)
            "slug": slug,
            "kind": kind,
            "status": "draft",
            "tier": "plain" if kind == "common" else kind,
            "topic_id": topic.get("id"),
        }
        resp = await client.table("challenges").insert(payload).execute()
        if not resp.data:
            raise RuntimeError(f"Failed to create challenge kind={kind}")
        return resp.data[0]

    def _make_common_specs(self) -> List[Tuple[str, int]]:
        # (tier, points)
        return [("bronze", 10), ("bronze", 10), ("bronze", 10), ("silver", 20), ("gold", 30)]

    def _make_single_spec(self, kind: str) -> Tuple[str, int]:
        mapping = {"ruby": ("ruby", 40), "platinum": ("platinum", 60), "diamond": ("diamond", 100)}
        return mapping.get(kind, ("bronze", 10))

    async def _create_question_from_template(self, challenge_id: str, tier: str, points: int) -> Dict[str, Any]:
        # Prefer AI-generated spec (Mistral via Hugging Face) with fallback to static template
        try:
            tpl = await generate_question_spec(slide_texts=None, week=self.week, topic=None, kind="common", tier=tier)
        except Exception:
            tpl = template_reverse_string()
        language_id = tpl.get("language_id", 28)
        starter_code = tpl.get("starter_code")
        reference_solution = tpl.get("reference_solution")
        tests: List[Dict[str, str]] = list(tpl.get("tests", []))
        # For MVP, set expected_output to first public test's expected so single-run compares work
        first_public = next((t for t in tests if (t.get("visibility") == "public")), tests[0] if tests else None)
        expected_output = (first_public or {}).get("expected") if first_public else None
        payload = {
            "challenge_id": challenge_id,
            "language_id": int(language_id),
            "expected_output": expected_output,
            "points": points,
            "starter_code": starter_code,
            "max_time_ms": tpl.get("max_time_ms", 2000),
            "max_memory_kb": tpl.get("max_memory_kb", 256000),
            "tier": tier,
        }
        q = await question_repository.create_question(payload)
        # Insert tests rows
        await question_repository.insert_tests(str(q["id"]), tests)

        # Validate reference solution against all tests
        if reference_solution and tests:
            items = [
                {
                    "language_id": int(language_id),
                    "source": reference_solution,
                    "stdin": t.get("input"),
                    "expected": t.get("expected"),
                }
                for t in tests
            ]
            results = await run_many(items)
            all_pass = all(r.get("success") for r in results)
            if all_pass:
                # Mark valid if column exists; ignore if not
                try:
                    client = await get_supabase()
                    await client.table("questions").update({"valid": True}).eq("id", q["id"]).execute()
                except Exception:
                    pass
        return q

    async def generate(self) -> Dict[str, Any]:
        topic = await self._ensure_topic()
        created: Dict[str, Optional[Dict[str, Any]]] = {"common": None, "ruby": None, "platinum": None}

        # Common (always)
        common = await self._create_challenge("common", topic)
        # Create 5 questions for common
        for tier, pts in self._make_common_specs():
            await self._create_question_from_template(str(common["id"]), tier=tier, points=pts)
        created["common"] = {"challenge_id": str(common["id"]) }

        # Ruby every 2nd week
        if self.week % 2 == 0:
            ruby = await self._create_challenge("ruby", topic)
            t, pts = self._make_single_spec("ruby")
            await self._create_question_from_template(str(ruby["id"]), tier=t, points=pts)
            created["ruby"] = {"challenge_id": str(ruby["id"]) }

        # Platinum every 4th week
        if self.week % 4 == 0:
            plat = await self._create_challenge("platinum", topic)
            t, pts = self._make_single_spec("platinum")
            await self._create_question_from_template(str(plat["id"]), tier=t, points=pts)
            created["platinum"] = {"challenge_id": str(plat["id"]) }

        return {
            "week": self.week,
            "topic": {"slug": topic.get("slug"), "title": topic.get("title")},
            "created": created,
            "status": "draft",
        }


# Simple facade preserved for potential importers
async def generate_week(week_number: int, slides_url: str, force: bool = False) -> Dict[str, Any]:
    return await WeeksOrchestrator(week=week_number, slides_url=slides_url, force=force).generate()
