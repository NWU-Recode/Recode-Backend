import asyncio
import os
from app.features.challenges import challenge_pack_generator
from app.features.challenges.templates.strings import get_fallback_payload

# Fake invoke that returns fallback payloads based on the prompt (tier)
async def _fake_invoke(prompt: str):
    prompt_lower = (prompt or "").lower()
    if "emerald" in prompt_lower:
        return get_fallback_payload("emerald", 1, "Fallback Topic")
    if "diamond" in prompt_lower:
        return get_fallback_payload("diamond", 1, "Fallback Topic")
    if "ruby" in prompt_lower:
        return get_fallback_payload("ruby", 1, "Fallback Topic")
    return get_fallback_payload("base", 1, "Fallback Topic")

async def main():
    # Patch the generator module to use the fake invoke
    try:
        challenge_pack_generator.invoke_model = _fake_invoke
    except Exception:
        pass

    # Parameters for the run
    week = int(os.environ.get("GEN_WEEK", "1"))
    module_code = os.environ.get("GEN_MODULE_CODE")
    lecturer_id = int(os.environ.get("GEN_LECTURER_ID", "1"))

    print(f"Running generation for week={week}, module_code={module_code}, lecturer_id={lecturer_id}")
    gen = challenge_pack_generator.ChallengePackGenerator(
        week,
        slide_stack_id=None,
        module_code=module_code,
        lecturer_id=lecturer_id,
    )
    result = await gen.generate()
    print("Generation result:")
    print(result)

if __name__ == '__main__':
    asyncio.run(main())
