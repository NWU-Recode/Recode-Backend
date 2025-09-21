import boto3
import json
import os
from typing import Dict, Any
from app.Core.config import get_settings

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
                "content": prompt
            }
        ]
    }
    if safe_stops:
        payload["stop_sequences"] = safe_stops

    body = json.dumps(payload)
    
    response = bedrock.invoke_model(
        modelId=settings.bedrock_model_id,
        body=body,
        contentType="application/json",
        accept="application/json"
    )
    
    response_body = json.loads(response['body'].read())
    
    # Extract the JSON from Claude's response
    # Claude returns text that should be valid JSON matching the specified format
    try:
        result = json.loads(response_body['content'][0]['text'])
        # Validate the structure matches expected format
        if not isinstance(result, dict):
            raise ValueError("Response is not a JSON object")

        if 'challenge_set_title' not in result or 'questions' not in result:
            raise ValueError("Response missing required fields: challenge_set_title or questions")

        if not isinstance(result['questions'], list):
            raise ValueError("questions field must be an array")

        # Validate each question structure
        for i, question in enumerate(result['questions']):
            required_fields = ['title', 'question_text', 'difficulty_level', 'starter_code', 'reference_solution', 'test_cases']
            for field in required_fields:
                if field not in question:
                    raise ValueError(f"Question {i} missing required field: {field}")

            if not isinstance(question['test_cases'], list):
                raise ValueError(f"Question {i} test_cases must be an array")

            # Validate difficulty levels
            valid_difficulties = ['Bronze', 'Silver', 'Gold', 'Ruby', 'Emerald', 'Diamond']
            if question['difficulty_level'] not in valid_difficulties:
                raise ValueError(f"Question {i} has invalid difficulty_level: {question['difficulty_level']}")

        return result
    except (KeyError, json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Failed to parse Claude response: {e}")