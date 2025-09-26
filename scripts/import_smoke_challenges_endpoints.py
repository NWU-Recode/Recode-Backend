# simple import smoke-test for challenges endpoints
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import app.features.challenges.endpoints as ep
    print('import OK')
except Exception as e:
    import traceback
    traceback.print_exc()
    print('import FAILED:', e)
