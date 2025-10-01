"""Utility script to exercise the /judge0/submit/poll endpoint on a local dev server.

Usage:
    python scripts/test_submit_poll_local.py --host http://127.0.0.1:8000 \
        --source "print(1+1)" --language-id 71

It submits a small payload, waits for the JSON response, and prints a friendly summary.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import httpx


DEFAULT_HOST = "http://127.0.0.1:8000"
DEFAULT_SOURCE = "print('Hello Judge0!')"
DEFAULT_LANGUAGE_ID = 71  # Python 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test for /judge0/submit/poll endpoint")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Base URL of the backend (default: %(default)s)")
    parser.add_argument(
        "--path",
        default="/judge0/submit/poll",
        help="Endpoint path to test (default: %(default)s)",
    )
    parser.add_argument(
        "--source",
        default=DEFAULT_SOURCE,
        help="Source code to submit (default: %(default)s)",
    )
    parser.add_argument(
        "--language-id",
        type=int,
        default=DEFAULT_LANGUAGE_ID,
        help="Judge0 language id (default: %(default)s)",
    )
    parser.add_argument(
        "--stdin",
        default=None,
        help="Optional stdin payload (default: %(default)s)",
    )
    parser.add_argument(
        "--expected",
        default=None,
        help="Optional expected_output for Judge0 (default: %(default)s)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds (default: %(default)s)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    url = args.host.rstrip("/") + args.path
    payload: dict[str, Any] = {
        "source_code": args.source,
        "language_id": args.language_id,
    }
    if args.stdin is not None:
        payload["stdin"] = args.stdin
    if args.expected is not None:
        payload["expected_output"] = args.expected

    print(f"Submitting payload to {url} ...")
    try:
        with httpx.Client(timeout=args.timeout) as client:
            response = client.post(url, json=payload)
    except Exception as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1

    print(f"HTTP {response.status_code}")
    try:
        data = response.json()
    except Exception:
        print("Response body (non-JSON):")
        print(response.text)
        return 1 if response.status_code >= 400 else 0

    print("JSON response:")
    print(json.dumps(data, indent=2))

    # Provide a condensed summary if the result payload looks familiar
    result = data if isinstance(data, dict) else None
    if result:
        token = result.get("token")
        status = None
        if isinstance(result.get("result"), dict):
            status = result["result"].get("status_id")
        elif result.get("status_id") is not None:
            status = result.get("status_id")
        if token or status is not None:
            print("-- Summary --")
            print(f"token: {token}")
            print(f"status_id: {status}")
    return 0 if response.status_code < 400 else 1


if __name__ == "__main__":
    raise SystemExit(main())
