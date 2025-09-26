import asyncio
import sys
from pathlib import Path
# add project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.features.challenges.challenge_pack_generator import generate_and_save_tier

async def main():
    try:
        res = await generate_and_save_tier('base', week=1, slide_stack_id=None, module_code=None, lecturer_id=1)
        print('RESULT:', res)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())
