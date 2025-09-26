import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    import app.features.challenges.endpoints as e
    print('import ok:', e)
except Exception as ex:
    import traceback
    traceback.print_exc()
