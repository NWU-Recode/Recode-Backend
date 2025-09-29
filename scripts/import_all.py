"""
Simple import checker that walks the `app` package and tries to import each module.
Run from repo root: python scripts/import_all.py
"""
import sys
import pkgutil
import importlib
import traceback
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

failures = []
imported = []

# Attempt to import the top-level 'app' package
try:
    import app  # type: ignore
except Exception:
    print('IMPORT_FAIL: could not import top-level package "app"')
    traceback.print_exc()
    raise SystemExit(2)

# Walk the app package modules
for finder, name, ispkg in pkgutil.walk_packages(app.__path__, prefix=app.__name__ + "."):
    # Skip tests or heavy scripts if necessary by pattern (none here)
    try:
        importlib.import_module(name)
        imported.append(name)
    except Exception as e:
        failures.append((name, traceback.format_exc()))

print('\nImported modules: ', len(imported))
if failures:
    print('\nIMPORT FAILURES (count=%d):' % len(failures))
    for mod, tb in failures:
        print('--- Failed:', mod)
        print(tb)
    raise SystemExit(3)
else:
    print('\nIMPORT_OK: all app modules imported successfully')
    raise SystemExit(0)
