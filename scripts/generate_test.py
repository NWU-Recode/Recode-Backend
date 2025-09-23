import asyncio
from app.features.challenges import claude_generator
from app.features.challenges.claude_generator import _fetch_topic_context, generate_tier_preview, _call_bedrock
from app.features.challenges.templates.strings import get_fallback_payload
from app.features.challenges.ai import bedrock_client

# Monkeypatch the Bedrock/Claude client to return the fallback payload
async def _fake_invoke(prompt: str):
    # determine kind by simplistic check
    if "emerald" in prompt.lower():
        return get_fallback_payload("emerald", 1, "Fallback Topic")
    if "diamond" in prompt.lower():
        return get_fallback_payload("diamond", 1, "Fallback Topic")
    if "ruby" in prompt.lower():
        return get_fallback_payload("ruby", 1, "Fallback Topic")
    return get_fallback_payload("base", 1, "Fallback Topic")


async def main():
    week = 1
    # Patch the bedrock invoke to avoid external calls
    # claude_generator imported invoke_claude directly at module import time,
    # so replace the name in that module to ensure the fake is used.
    try:
        claude_generator.invoke_claude = _fake_invoke
    except Exception:
        pass
    # fetch context
    context = await _fetch_topic_context(week, slide_stack_id=None, module_code=None, tier="base")
    print("Topic context:", context)

    # preview base tier using fallback payload directly
    preview = await generate_tier_preview("base", week, module_code=None)
    print("Preview:", preview)

if __name__ == '__main__':
    asyncio.run(main())
