import os
import json
from fastapi.testclient import TestClient
from app.main import app

BEARER = os.environ.get("BEARER")
if not BEARER:
    print("Missing BEARER environment variable. Set BEARER to the token string.")
    raise SystemExit(1)

client = TestClient(app)
headers = {"Authorization": f"Bearer {BEARER}"}

# Truncate helper
def short(s, n=300):
    t = s if isinstance(s, str) else json.dumps(s)
    return t if len(t) <= n else t[:n] + "..."

results = []

def do_request(method, path, **kwargs):
    try:
        fn = getattr(client, method.lower())
        resp = fn(path, headers=headers, timeout=10, **kwargs)
        text = resp.text
        results.append((method, path, resp.status_code, short(text)))
    except Exception as e:
        results.append((method, path, 'EXC', repr(e)))

# Basic paths and sample payloads
paths = [
    ("GET", "/admin/me"),
    ("GET", "/admin"),
    ("POST", "/admin/", {"json": {"code": "TEST101", "name": "Test Module", "description": "Auto-created by admin_check"}}),
    ("PUT", "/admin/TEST101", {"json": {"code": "TEST101", "name": "Test Module Updated"}}),
    ("GET", "/admin/TEST101"),
    ("GET", "/admin/TEST101/students"),
    ("GET", "/admin/TEST101/challenges"),
    ("POST", "/admin/TEST101/enrol", {"json": {"student_id": 1}}),
    ("POST", "/admin/TEST101/enrol/batch", {"json": {"student_ids": [1,2]}}),
    ("POST", "/admin/TEST101/enrol/upload", {"files": {"file": ("dummy.csv", "student_id\n1\n2\n", "text/csv")}}),
    ("POST", "/admin/TEST101/assign-lecturer", {"json": {"lecturer_id": 1}}),
    ("POST", "/admin/TEST101/remove-lecturer", {}),
    ("POST", "/admin/assign-lecturer", {"json": {"module_code": "TEST101", "lecturer_id": 1}}),
    ("POST", "/admin/remove-lecturer", {"json": {"module_code": "TEST101"}}),
    ("POST", "/admin/semesters", {"json": {"year": 2025, "term_name": "S1", "start_date": "2025-01-01", "end_date": "2025-06-01", "is_current": False}}),
    ("POST", "/admin/demo/skip", {"json": {"delta": 1}}),
    ("POST", "/admin/demo/set", {"json": {"offset": 0}}),
    ("DELETE", "/admin/demo/clear", {}),
]

for item in paths:
    method, path = item[0], item[1]
    kwargs = item[2] if len(item) > 2 else {}
    print(f"Calling {method} {path} ...")
    do_request(method, path, **kwargs)

print("\nResults:\n")
for r in results:
    method, path, status, text = r
    print(f"{method} {path} -> {status}\n{text}\n---")

# Exit with non-zero if any 5xx errors occurred
exit_code = 0
for _, _, status, _ in results:
    try:
        if isinstance(status, int) and 500 <= status < 600:
            exit_code = 2
    except Exception:
        exit_code = 1

raise SystemExit(exit_code)
