from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from app.Core.config import get_settings

settings = get_settings()

bedrock = boto3.client(
    service_name="bedrock-runtime",
    region_name=settings.aws_region,
    aws_access_key_id=settings.aws_access_key_id,
    aws_secret_access_key=settings.aws_secret_access_key,
)


async def invoke_claude(prompt: str, max_tokens: Optional[int] = None) -> Dict[str, Any]:
    """Invoke the configured Claude model on AWS Bedrock and return a validated JSON payload."""
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

    try:
        response_body = await _invoke(payload)
    except ClientError as ce:
        message = str(ce)
        if "ValidationException" in message and "stop_sequences" in message:
            payload.pop("stop_sequences", None)
            response_body = await _invoke(payload)
        else:
            raise

    full_text = _extract_text(response_body)
    if not full_text and payload.get("stop_sequences"):
        try:
            payload.pop("stop_sequences", None)
            response_body = await _invoke(payload)
            full_text = _extract_text(response_body)
        except Exception:
            full_text = ""

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
        return json.loads(cleaned)

    try:
        if not full_text:
            raise ValueError(f"Empty response content: {json.dumps(response_body)[:500]}")

        result = _try_parse_json(full_text)
        if not isinstance(result, dict):
            raise ValueError("Response is not a JSON object")
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
        raise ValueError(f"Failed to parse Claude response: {exc}")
