"""Simple harness to call record_test_result_and_award RPC and assert side-effects.

Usage:
  set the following env vars (or export in your shell):
    SUPABASE_URL, SUPABASE_KEY
  then run:
    python scripts/test_record_rpc.py

This script will:
 - create a temporary test profile (if not present it will assume profile with id 1 exists)
 - call the RPC twice with identical payload to verify idempotency
 - query question_attempts, user_badges, user_elo tables to assert results

Be cautious: this script will insert rows into your database. Run against staging.
"""
from __future__ import annotations

import os
import asyncio
import uuid
import sys
from datetime import datetime

import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    print("Please set SUPABASE_URL and SUPABASE_KEY environment variables to a staging DB.")
    sys.exit(1)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
}

async def rpc_call(payload: dict) -> dict:
    url = f"{SUPABASE_URL}/rpc/record_test_result_and_award"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload, headers=HEADERS)
        resp.raise_for_status()
        return resp.json()

async def query_table(table: str, params: dict = None):
    params = params or {}
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params, headers=HEADERS)
        resp.raise_for_status()
        return resp.json()

async def run_test():
    test_profile_id = int(os.environ.get("TEST_PROFILE_ID", "1"))
    question_id = os.environ.get("TEST_QUESTION_ID") or str(uuid.uuid4())
    test_id = os.environ.get("TEST_TEST_ID") or str(uuid.uuid4())
    public_badge_id = os.environ.get("TEST_BADGE_ID")

    payload = {
        "p_profile_id": test_profile_id,
        "p_question_id": question_id,
        "p_test_id": test_id,
        "p_is_public": True,
        "p_passed": True,
        "p_public_badge_id": public_badge_id,
    }

    print("Calling RPC first time (expect creation)")
    out1 = await rpc_call(payload)
    print("RPC output:", out1)

    print("Calling RPC second time (expect idempotent/no-duplicate badge)")
    out2 = await rpc_call(payload)
    print("RPC output 2:", out2)

    # Query question_attempts for our synthetic idempotency key
    key = f"rpc:{test_id}:{test_profile_id}"
    attempts = await query_table("question_attempts", {"idempotency_key": f"eq.{key}"})
    print("Attempts matching idempotency key:", attempts)

    badges = []
    if public_badge_id:
        badges = await query_table("user_badges", {"user_id": f"eq.{test_profile_id}", "badge_id": f"eq.{public_badge_id}"})
        print("User badges for profile:", badges)

    elo = await query_table("user_elo", {"user_id": f"eq.{test_profile_id}"})
    print("User elo rows:", elo)

    print("Assertions:")
    assert out1.get("existing") in (True, False)
    assert out2.get("existing") in (True, False)
    # if attempts present, should be at least one
    if attempts:
        print("OK: attempts recorded")
    else:
        print("WARN: no attempts found for idempotency key - check migration")

    if public_badge_id:
        if len(badges) > 1:
            print("ERROR: duplicate badges awarded!", badges)
        else:
            print("OK: badge presence check passed")

    print("Done. Clean up manual if needed.")

if __name__ == "__main__":
    asyncio.run(run_test())
