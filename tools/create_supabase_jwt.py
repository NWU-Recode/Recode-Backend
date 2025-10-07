#!/usr/bin/env python3
"""
Generate a Supabase-compatible access JWT signed with the project's SUPABASE_JWT_SECRET.

Usage:
  python tools/create_supabase_jwt.py --user-id <uuid> [--days 30]

This script signs a token with HS256 and sets claims that GoTrue/Supabase accepts
for 'authenticated' sessions (aud, role). Use for local/dev/testing only.

Security: This requires your SUPABASE_JWT_SECRET (set in .env or env var). Do NOT
commit generated tokens or share them publicly.
"""
import os
import time
import argparse
from datetime import datetime, timedelta

try:
    import jwt
except Exception:
    raise SystemExit("Please install PyJWT: pip install PyJWT")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user-id", required=True, help="User UUID (sub claim)")
    p.add_argument("--days", type=int, default=30, help="Days until token expiry")
    p.add_argument("--secret", default=os.getenv("SUPABASE_JWT_SECRET"), help="SUPABASE_JWT_SECRET (or set in env)")
    args = p.parse_args()

    if not args.secret:
        print("Error: SUPABASE_JWT_SECRET not provided. Set it in your environment or pass --secret.")
        raise SystemExit(1)

    now = int(time.time())
    exp = now + args.days * 24 * 3600

    payload = {
        "sub": args.user_id,
        "aud": "authenticated",
        "role": "authenticated",
        "iat": now,
        "exp": exp,
    }

    token = jwt.encode(payload, args.secret, algorithm="HS256")

    print("\n=== Generated JWT (use as Authorization: Bearer <token>) ===\n")
    print(token)
    print("\nExpires at:", datetime.utcfromtimestamp(exp).isoformat() + "Z")


if __name__ == "__main__":
    main()
