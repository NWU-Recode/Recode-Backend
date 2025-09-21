from __future__ import annotations

import json
from typing import Any, Dict, List
from pathlib import Path

from app.Core.config import get_settings
from .bedrock_client import invoke_claude


def _load_template(kind: str) -> str:
    base_dir = Path(__file__).parent.parent / "prompts"
    fname = {
        "common": "claude_week_template.txt",
        "ruby": "hf_ruby_template.txt",
        "emerald": "hf_emerald_template.txt",
        "diamond": "hf_diamond_template.txt",
    }.get(kind, "claude_week_template.txt")
    path = base_dir / fname
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        # Fallback minimal template if file missing
        return (
            "You are an expert coding tutor. Generate JSON challenges for topics: {{topics_list}}. "
            "Return only valid JSON matching the specified format."
        )


def _build_prompt(slide_texts: List[str], week: int, topic: Dict[str, Any] | None, kind: str, tier: str) -> str:
    topic_title = (topic or {}).get("title") or (topic or {}).get("slug") or f"Week {week}"
    topic_slug = (topic or {}).get("slug") or ""
    detected_topic = (topic or {}).get("detected_topic") or ""
    detected_subtopics = (topic or {}).get("detected_subtopics") or ""
    topics_list = topic_title
    if slide_texts:
        lines = [ln.strip() for ln in slide_texts if ln and ln.strip()]
        topics_list = ", ".join(lines[:6])[:400]
    base = _load_template(kind)
    prompt = base.replace("{{topics_list}}", topics_list)
    prompt = prompt.replace("{{topic_slug}}", str(topic_slug))
    prompt = prompt.replace("{{detected_topic}}", str(detected_topic))
    prompt = prompt.replace("{{detected_subtopics}}", str(detected_subtopics))
    return prompt


async def generate_question_spec(
    slide_texts: List[str] | None,
    week: int,
    topic: Dict[str, Any] | None,
    kind: str,
    tier: str,
) -> Dict[str, Any]:
    """Generate question specifications using AWS Bedrock Claude."""
    prompt = _build_prompt(slide_texts or [], week, topic, kind, tier)

    try:
        # Call Claude via Bedrock
        response = await invoke_claude(prompt, max_tokens=8000)

        # Claude returns the full JSON structure we need
        if isinstance(response, dict) and "questions" in response:
            # For single question generation (ruby, emerald, diamond)
            if kind in ["ruby", "emerald", "diamond"] and response["questions"]:
                question = response["questions"][0]
                return {
                    "language_id": 71,  # Python 3.10 for Judge0
                    "starter_code": question.get("starter_code", ""),
                    "reference_solution": question.get("reference_solution", ""),
                    "tests": [
                        {
                            "input": tc.get("input", ""),
                            "expected": tc.get("expected", ""),
                            "visibility": "public"
                        }
                        for tc in question.get("test_cases", [])
                    ],
                    "max_time_ms": 2000,
                    "max_memory_kb": 256000,
                }
            # For common challenges (multiple questions)
            elif kind == "common" and len(response["questions"]) >= 5:
                # Return the full response for processing by challenge generation
                return response

        # Fallback for unexpected response format
        return {
            "language_id": 71,
            "starter_code": "",
            "reference_solution": "",
            "tests": [],
            "max_time_ms": 2000,
            "max_memory_kb": 256000,
        }

    except Exception as e:
        print(f"Error generating question spec with Claude: {e}")
        # Return minimal fallback
        return {
            "language_id": 71,
            "starter_code": "",
            "reference_solution": "",
            "tests": [],
            "max_time_ms": 2000,
            "max_memory_kb": 256000,
        }


__all__ = ["generate_question_spec"]
