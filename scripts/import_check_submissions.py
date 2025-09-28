import traceback
from pathlib import Path
import sys

print('running import check for app.features.submissions.endpoints')
try:
    # Add repository root to sys.path so `import app...` works when executing from scripts/
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    import importlib
    m = importlib.import_module('app.features.submissions.endpoints')
    importlib.reload(m)
    print('IMPORT_OK')
except Exception:
    print('IMPORT_ERROR')
    traceback.print_exc()
    raise
