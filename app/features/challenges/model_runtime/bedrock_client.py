from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError
import os
from datetime import datetime
import pathlib

from app.Core.config import get_settings

settings = get_settings()

bedrock = boto3.client(
    service_name="bedrock-runtime",
    region_name=settings.aws_region,
    aws_access_key_id=settings.aws_access_key_id,
    aws_secret_access_key=settings.aws_secret_access_key,
)


async def invoke_model(prompt: str, max_tokens: Optional[int] = None) -> Dict[str, Any]:
    """Invoke the configured Bedrock model and return a validated JSON payload."""
    if max_tokens is None:
        max_tokens = settings.bedrock_max_tokens

    raw_stops = settings.bedrock_stop_sequences or []
    safe_stops = [s for s in raw_stops if isinstance(s, str) and s.strip()]

    payload: Dict[str, Any] = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": settings.bedrock_temperature,
        "top_p": settings.bedrock_top_p,
        "top_k": settings.bedrock_top_k,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    }
    if safe_stops:
        payload["stop_sequences"] = safe_stops

    async def _invoke(payload_dict: Dict[str, Any]) -> Dict[str, Any]:
        loop = asyncio.get_running_loop()
        body_json = json.dumps(payload_dict)

        def _call() -> Dict[str, Any]:
            response = bedrock.invoke_model(
                modelId=settings.bedrock_model_id,
                body=body_json,
                contentType="application/json",
                accept="application/json",
            )
            return json.loads(response["body"].read())

        return await loop.run_in_executor(None, _call)

    def _extract_text(resp_body: Dict[str, Any]) -> str:
        content_list = resp_body.get("content") or []
        parts: List[str] = []
        for block in content_list:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts).strip()

    tick = chr(96)

    def _strip_code_fences(text: str) -> str:
        stripped = text.strip()
        if stripped.startswith(tick * 3):
            stripped = stripped.strip(tick)
            lowered = stripped.lower()
            if lowered.startswith("json"):
                stripped = stripped[4:].lstrip()
        return stripped

    def _try_parse_json(text: str) -> Any:
        for candidate in (text, _strip_code_fences(text)):
            try:
                return json.loads(candidate)
            except Exception:
                pass
        start = text.find("{")
        if start != -1:
            depth = 0
            for index, ch in enumerate(text[start:], start=start):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        slice_text = text[start : index + 1]
                        try:
                            return json.loads(slice_text)
                        except Exception:
                            break
        cleaned = text.strip().strip(tick)
        try:
            return json.loads(cleaned)
        except Exception:
            return None

    def _parse_markdown_response(text: str) -> Dict[str, Any]:
        """Parse markdown-formatted response into expected JSON structure."""
        lines = text.split('\n')
        title = ""
        questions = []
        current_question = None
        current_section = ""
        
        for line in lines:
            line = line.strip()
            if line.startswith('# ') and not title:
                title = line[2:].strip()
            elif line.startswith('## ') and '(' in line and 'Questions)' in line:
                # New section, but we'll assign difficulties later
                current_section = line.split('(')[0][3:].strip()
            elif line.startswith('### ') and current_question is None:
                if current_question:
                    questions.append(current_question)
                current_question = {
                    "title": line[4:].strip(),
                    "question_text": "",
                    "difficulty_level": "Bronze",  # Default, will be updated based on section
                    "starter_code": "",
                    "reference_solution": "",
                    "tests": []
                }
            elif current_question and line and not line.startswith('#'):
                current_question["question_text"] += line + "\n"
        
        if current_question:
            questions.append(current_question)
        
        # Worst Case Fallback Assign difficulties based on section
        difficulty_map = {
            "Variables": "Bronze",
            "Conditionals": "Silver", 
            "Loops": "Gold",
            "Functions": "Ruby",
            "Lists": "Emerald"
        }
        
        for question in questions:
            for section, diff in difficulty_map.items():
                if section.lower() in current_section.lower():
                    question["difficulty_level"] = diff
                    break
        
        return {
            "challenge_set_title": title or "Programming Questions",
            "questions": questions
        }

    def _coerce_json(value: Any) -> Any:
        while isinstance(value, str):
            value = json.loads(value)
        return value

    def _ensure_dict(value: Any, error_message: str) -> Dict[str, Any]:
        coerced = _coerce_json(value)
        if not isinstance(coerced, dict):
            raise ValueError(error_message)
        return coerced

    try:
        try:
            raw_response = await _invoke(payload)
        except ClientError as ce:
            message = str(ce)
            if "ValidationException" in message and "stop_sequences" in message:
                payload.pop("stop_sequences", None)
                raw_response = await _invoke(payload)
            else:
                raise

        response_body = _ensure_dict(raw_response, "Bedrock response is not a JSON object")
        full_text = _extract_text(response_body)

        if not full_text and payload.get("stop_sequences"):
            try:
                payload.pop("stop_sequences", None)
                retry_response = await _invoke(payload)
                response_body = _ensure_dict(retry_response, "Bedrock response is not a JSON object")
                full_text = _extract_text(response_body)
            except Exception:
                full_text = ""

        if not full_text:
            raise ValueError(f"Empty response content: {json.dumps(response_body)[:500]}")

        parsed = _try_parse_json(full_text)
        if parsed is None:
            # Try parsing as markdown
            try:
                parsed = _parse_markdown_response(full_text)
            except Exception:
                raise ValueError("Response is neither valid JSON nor parseable markdown")
        result = _ensure_dict(parsed, "Response is not a JSON object")

        if "challenge_set_title" not in result or "questions" not in result:
            raise ValueError("Response missing required fields: challenge_set_title or questions")
        if not isinstance(result["questions"], list):
            raise ValueError("questions field must be an array")

        valid_difficulties = {"Bronze", "Silver", "Gold", "Ruby", "Emerald", "Diamond"}
        for index, question in enumerate(result["questions"]):
            required_fields = ["title", "question_text", "difficulty_level", "starter_code", "reference_solution"]
            for field in required_fields:
                if field not in question:
                    raise ValueError(f"Question {index} missing required field: {field}")
            difficulty = question.get("difficulty_level")
            if difficulty not in valid_difficulties:
                raise ValueError(f"Question {index} has invalid difficulty_level: {difficulty}")
            tests = question.get("tests")
            if tests is not None:
                if not isinstance(tests, list):
                    raise ValueError(f"Question {index} has non-list tests field")
                for test in tests:
                    if not isinstance(test, dict):
                        raise ValueError(f"Question {index} has invalid test item: {test}")
                    if "input" not in test or "expected" not in test:
                        raise ValueError(f"Question {index} test missing input/expected")
                    visibility = str(test.get("visibility", "private"))
                    if visibility not in {"public", "private"}:
                        raise ValueError(f"Question {index} test has invalid visibility: {visibility}")

        return result
    except (KeyError, json.JSONDecodeError, ValueError) as exc:
        # Optional: dump raw response and prompt payload for debugging
        try:
            if os.environ.get("BEDROCK_DUMP_RAW", "0") in {"1", "true", "True"}:
                dump_dir = pathlib.Path("logs")
                dump_dir.mkdir(parents=True, exist_ok=True)
                ts = datetime.utcnow().isoformat(timespec="seconds").replace(":", "-")
                dump_path = dump_dir / f"bedrock_raw_{ts}.json"
                dump_content = {
                    "payload": payload,
                    "response_body": response_body if 'response_body' in locals() else None,
                    "full_text": full_text if 'full_text' in locals() else None,
                }
                try:
                    dump_path.write_text(json.dumps(dump_content, default=str, indent=2), encoding="utf-8")
                    print(f"[bedrock-debug] dumped raw response to: {dump_path}")
                except Exception:
                    pass
        except Exception:
            pass
        raise ValueError(f"Failed to parse model response: {exc}")
