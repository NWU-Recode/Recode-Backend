import boto3
import json
import os
import re
from typing import Dict, Any
from app.Core.config import get_settings
from botocore.exceptions import ClientError

settings = get_settings()

bedrock = boto3.client(
    service_name="bedrock-runtime",
    region_name=settings.aws_region,
    aws_access_key_id=settings.aws_access_key_id,
    aws_secret_access_key=settings.aws_secret_access_key
)

def invoke_claude(prompt: str, max_tokens: int = None) -> Dict[str, Any]:
    """
    Invoke Claude model via AWS Bedrock.
    
    Args:
        prompt: The prompt to send to Claude
        max_tokens: Maximum tokens to generate (optional, uses config default)
        
    Returns:
        Parsed JSON response from Claude
    """
    if max_tokens is None:
        max_tokens = settings.bedrock_max_tokens
    
    # Sanitize stop sequences: remove empty/whitespace-only entries
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
                    {"type": "text", "text": prompt}
                ]
            }
        ]
    }
    if safe_stops:
        payload["stop_sequences"] = safe_stops

    body = json.dumps(payload)
    
    def _invoke(body_json: str):
        return bedrock.invoke_model(
            modelId=settings.bedrock_model_id,
            body=body_json,
            contentType="application/json",
            accept="application/json"
        )

    def _extract_text(resp_body: Dict[str, Any]) -> str:
        content_list = resp_body.get('content') or []
        text_parts = []
        for block in content_list:
            if isinstance(block, dict) and block.get('type') == 'text':
                text_parts.append(block.get('text') or '')
            elif isinstance(block, str):
                text_parts.append(block)
        return ''.join(text_parts).strip()

    try:
        response = _invoke(body)
    except ClientError as ce:
        msg = str(ce)
        if "ValidationException" in msg and "stop_sequences" in msg:
            # Retry without stop sequences
            try:
                payload.pop("stop_sequences", None)
                body_no_stops = json.dumps(payload)
                response = _invoke(body_no_stops)
            except Exception as e2:
                raise ValueError(f"Bedrock invoke failed after removing stop_sequences: {e2}")
        else:
            raise

    response_body = json.loads(response['body'].read())

    # If we got no content due to early stop on a stop_sequence, retry once without stop sequences
    full_text = _extract_text(response_body)
    if not full_text and payload.get("stop_sequences"):
        stop_reason = response_body.get('stop_reason')
        if stop_reason == 'stop_sequence':
            try:
                payload.pop("stop_sequences", None)
                response = _invoke(json.dumps(payload))
                response_body = json.loads(response['body'].read())
                full_text = _extract_text(response_body)
            except Exception as e:
                # fall through to normal error handling
                full_text = ""

    # Extract the JSON from Claude's response
    # Claude returns text that should be valid JSON matching the specified format
    def _try_parse_json(text: str) -> Any:
        # direct
        try:
            return json.loads(text)
        except Exception:
            pass
        # strip code fences ```json ... ``` or ``` ... ```
        fence_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL | re.IGNORECASE)
        if fence_match:
            inner = fence_match.group(1).strip()
            try:
                return json.loads(inner)
            except Exception:
                pass
        # extract first balanced JSON object
        start = text.find('{')
        if start != -1:
            depth = 0
            for i, ch in enumerate(text[start:], start=start):
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        candidate = text[start:i+1]
                        try:
                            return json.loads(candidate)
                        except Exception:
                            break
        # last attempt: remove leading/trailing junk and try again
        cleaned = text.strip().lstrip('`').rstrip('`').strip()
        return json.loads(cleaned)

    try:
        if not full_text:
            raise ValueError(f"Empty response content: {json.dumps(response_body)[:500]}")

        result = _try_parse_json(full_text)
        # Validate the structure matches expected format
        if not isinstance(result, dict):
            raise ValueError("Response is not a JSON object")

        if 'challenge_set_title' not in result or 'questions' not in result:
            raise ValueError("Response missing required fields: challenge_set_title or questions")

        if not isinstance(result['questions'], list):
            raise ValueError("questions field must be an array")

        # Validate each question structure
        for i, question in enumerate(result['questions']):
            required_fields = ['title', 'question_text', 'difficulty_level', 'starter_code', 'reference_solution']
            for field in required_fields:
                if field not in question:
                    raise ValueError(f"Question {i} missing required field: {field}")

            # Validate difficulty levels
            valid_difficulties = ['Bronze', 'Silver', 'Gold', 'Ruby', 'Emerald', 'Diamond']
            if question['difficulty_level'] not in valid_difficulties:
                raise ValueError(f"Question {i} has invalid difficulty_level: {question['difficulty_level']}")

        return result
    except (KeyError, json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Failed to parse Claude response: {e}")