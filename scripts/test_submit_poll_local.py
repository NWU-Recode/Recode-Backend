import httpx
import json

url = 'http://127.0.0.1:8000/judge0/submit/poll'
payload = {
    "source_code": "print('Polling DB!')",
    "language_id": 71
}

with httpx.Client(timeout=30) as c:
    r = c.post(url, json=payload)
    print('status_code=', r.status_code)
    try:
        print('json=', json.dumps(r.json(), indent=2))
    except Exception:
        print('text=', r.text)
