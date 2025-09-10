#!/usr/bin/env python3
"""Tiny async HTTP benchmarker for local testing.

Usage examples (PowerShell / CMD friendly):

  # 1) Start the app locally in a separate terminal
  #    > uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2

  # 2) Hit a public endpoint
  #    > python scripts/bench.py http://127.0.0.1:8000/healthz -c 20 -n 200

  # 3) Login first, then hit a protected endpoint using the same client cookies
  #    > python scripts/bench.py http://127.0.0.1:8000/auth/me -c 10 -n 50 \
  #        --login-email you@example.com --login-password yourpass

"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from typing import Dict, List, Optional

import httpx


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    k = max(0, min(len(values) - 1, int(round((p / 100.0) * (len(values) - 1)))))
    return sorted(values)[k]


async def _login_if_needed(client: httpx.AsyncClient, args: argparse.Namespace) -> None:
    if not (args.login_email and args.login_password):
        return
    url = args.login_url or "http://127.0.0.1:8000/auth/login"
    payload = {"email": args.login_email, "password": args.login_password}
    r = await client.post(url, json=payload)
    if args.debug:
        body_preview = r.text[:200].replace("\n", " ")
        print(f"[debug] login status={r.status_code} body={body_preview}")
        print(f"[debug] cookies after login: {client.cookies}")
    if r.status_code != 200:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise SystemExit(f"Login failed: {r.status_code} {detail}")
    # Extract access_token and keep as Authorization header fallback (avoids secure-cookie on http)
    try:
        data = r.json()
        token = (data or {}).get("access_token")
        if token:
            setattr(args, "_bearer_token", token)
            if args.debug:
                print("[debug] captured access_token for Authorization header")
    except Exception:
        pass


async def run_once(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: Dict[str, str] | None,
    json_body: Optional[dict],
) -> tuple[float, int, str]:
    t0 = time.perf_counter()
    try:
        if method == "GET":
            r = await client.get(url, headers=headers)
        elif method == "POST":
            r = await client.post(url, headers=headers, json=json_body)
        elif method == "PUT":
            r = await client.put(url, headers=headers, json=json_body)
        elif method == "DELETE":
            r = await client.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported method: {method}")
        status = r.status_code
        body = r.text
    except Exception:
        status = 0
        body = ""
    dt = (time.perf_counter() - t0) * 1000.0
    return dt, status, body


async def bench(args: argparse.Namespace) -> None:
    timeout = httpx.Timeout(connect=3.0, read=args.read_timeout, write=5.0, pool=5.0)
    limits = httpx.Limits(max_connections=max(20, args.concurrency * 2), max_keepalive_connections=max(10, args.concurrency))
    headers: Dict[str, str] = {}
    for item in args.header or []:
        if ":" in item:
            k, v = item.split(":", 1)
            headers[k.strip()] = v.strip()
    json_body = None
    if args.json:
        try:
            json_body = json.loads(args.json)
        except Exception as e:
            raise SystemExit(f"Invalid --json payload: {e}")

    async with httpx.AsyncClient(timeout=timeout, limits=limits, follow_redirects=args.follow_redirects) as client:
        await _login_if_needed(client, args)
        # Inject Authorization header after login if we captured a token and user didn't already set it
        if getattr(args, "_bearer_token", None) and not any(h.lower() == "authorization" for h in headers.keys()):
            headers["Authorization"] = f"Bearer {getattr(args, '_bearer_token')}"
            if args.debug:
                print("[debug] using Authorization header from captured access_token")

        # Warm-up
        try:
            await client.get(args.url)
        except Exception:
            pass

        latencies: List[float] = []
        codes: Dict[int, int] = {}
        pending = args.requests
        sem = asyncio.Semaphore(args.concurrency)
        debug_prints = 0

        async def worker():
            nonlocal pending
            nonlocal debug_prints
            while True:
                async with sem:
                    if pending <= 0:
                        return
                    pending -= 1
                dt, code, body = await run_once(client, args.method, args.url, headers, json_body)
                latencies.append(dt)
                codes[code] = codes.get(code, 0) + 1
                if args.debug and debug_prints < args.max_debug_prints:
                    body_preview = (body[:120].replace("\n", " ") if body else "")
                    print(f"[debug] {args.method} {args.url} -> {code} in {dt:.1f}ms body={body_preview}")
                    debug_prints += 1
                if args.fail_fast and not (200 <= code < 400):
                    raise SystemExit(f"Fail-fast: received status {code}")

        t0 = time.perf_counter()
        await asyncio.gather(*[asyncio.create_task(worker()) for _ in range(args.concurrency)])
        total_s = time.perf_counter() - t0

        ok = sum(v for k, v in codes.items() if 200 <= k < 400)
        err = args.requests - ok
        rps = args.requests / total_s if total_s > 0 else 0.0
        mean = statistics.mean(latencies) if latencies else 0.0
        p50 = _percentile(latencies, 50)
        p90 = _percentile(latencies, 90)
        p99 = _percentile(latencies, 99)

        print(f"URL: {args.url}")
        print(f"Method: {args.method}  Concurrency: {args.concurrency}  Requests: {args.requests}")
        print(f"Total time: {total_s:.2f}s  RPS: {rps:.1f}  OK: {ok}  ERR: {err}")
        print(f"Latency ms -> mean: {mean:.1f}  p50: {p50:.1f}  p90: {p90:.1f}  p99: {p99:.1f}")
        # Show top status codes
        top = sorted(codes.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
        print("Status codes:", ", ".join(f"{k}:{v}" for k, v in top))


def main() -> None:
    ap = argparse.ArgumentParser(description="Tiny async HTTP benchmarker")
    ap.add_argument("url", help="Target URL, e.g., http://127.0.0.1:8000/healthz")
    ap.add_argument("-c", "--concurrency", type=int, default=10)
    ap.add_argument("-n", "--requests", type=int, default=100)
    ap.add_argument("-X", "--method", default="GET", choices=["GET", "POST", "PUT", "DELETE"])
    ap.add_argument("--json", help="Inline JSON body for POST/PUT")
    ap.add_argument("-H", "--header", action="append", help="Header (Key: Value)")
    ap.add_argument("--login-email")
    ap.add_argument("--login-password")
    ap.add_argument("--login-url", help="Login URL (defaults to /auth/login)")
    ap.add_argument("--read-timeout", type=float, default=15.0, help="Read timeout seconds")
    ap.add_argument("--debug", action="store_true", help="Verbose: print login status, cookies, and per-request details")
    ap.add_argument("--max-debug-prints", type=int, default=10, help="Max per-request debug lines to print")
    ap.add_argument("--fail-fast", action="store_true", help="Stop on first non-2xx/3xx response")
    ap.add_argument("--follow-redirects", action="store_true", help="Follow HTTP redirects (e.g., /profiles -> /profiles/)")
    args = ap.parse_args()
    asyncio.run(bench(args))


if __name__ == "__main__":
    main()
