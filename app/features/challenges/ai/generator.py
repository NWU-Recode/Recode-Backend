from __future__ import annotations

import json
from typing import Any, Dict, List
from pathlib import Path

import httpx

from app.Core.config import get_settings


def _load_template(kind: str) -> str:
    base_dir = Path(__file__).parent.parent / "prompts"
    fname = {
        "common": "hf_week_template.txt",
        "ruby": "hf_ruby_template.txt",
        "emerald": "hf_emerald_template.txt",
        "diamond": "hf_diamond_template.txt",
        # Map platinum to emerald-style (hard, integrated)
        "platinum": "hf_emerald_template.txt",
    }.get(kind, "hf_week_template.txt")
    path = base_dir / fname
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        # Fallback minimal template if file missing
        return (
            "You are an expert coding tutor. Generate one JSON question for topics: {{topics_list}}. "
            "Return only JSON with keys: language_id, starter_code, reference_solution, tests."
        )


def _build_prompt(slide_texts: List[str], week: int, topic: Dict[str, Any] | None, kind: str, tier: str) -> str:
    topic_title = (topic or {}).get("title") or (topic or {}).get("slug") or f"Week {week}"
    topics_list = topic_title
    if slide_texts:
        lines = [ln.strip() for ln in slide_texts if ln and ln.strip()]
        topics_list = ", ".join(lines[:6])[:400]
    base = _load_template(kind)
    return base.replace("{{topics_list}}", topics_list)


async def generate_question_spec(
    slide_texts: List[str] | None,
    week: int,
    topic: Dict[str, Any] | None,
    kind: str,
    tier: str,
) -> Dict[str, Any]:
    settings = get_settings()
    model_id = settings.hf_model_id
    api_token = settings.hf_api_token
    timeout = settings.hf_timeout_ms / 1000.0

    prompt = _build_prompt(slide_texts or [], week, topic, kind, tier)
    headers = {"Content-Type": "application/json"}
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"

    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 800,
            "temperature": 0.2,
            "return_full_text": False,
        }
    }

    url = f"https://api-inference.huggingface.co/models/{model_id}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, headers=headers, json=payload)
    if resp.status_code >= 400:
        raise RuntimeError(f"HF API error {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    if isinstance(data, list) and data and isinstance(data[0], dict) and "generated_text" in data[0]:
        text = data[0]["generated_text"]
    elif isinstance(data, dict) and "generated_text" in data:
        text = data["generated_text"]
    else:
        text = data if isinstance(data, str) else json.dumps(data)

    try:
        spec = json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            spec = json.loads(text[start:end+1])
        else:
            raise RuntimeError("HF output not valid JSON")

    if isinstance(spec, dict) and "questions" in spec and isinstance(spec["questions"], list) and spec["questions"]:
        first = spec["questions"][0]
        out = {
            "language_id": 28,
            "starter_code": first.get("starter_code") or "",
            "reference_solution": first.get("reference_solution") or "",
            "tests": [
                {"input": tc.get("input"), "expected": tc.get("expected"), "visibility": "public"}
                for tc in (first.get("test_cases") or [])
            ],
            "max_time_ms": 2000,
            "max_memory_kb": 256000,
        }
        return out
    spec.setdefault("language_id", 28)
    spec.setdefault("tests", [])
    spec.setdefault("max_time_ms", 2000)
    spec.setdefault("max_memory_kb", 256000)
    return spec


__all__ = ["generate_question_spec"]
