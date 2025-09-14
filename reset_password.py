#!/usr/bin/env python3
"""
Interactive Supabase password reset tool.

Usage:
  - Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set in your environment (or paste when prompted).
  - Run: python scripts/reset_password.py
  - Paste a user UUID when prompted. Repeat as needed. Ctrl+C to quit.
"""
from __future__ import annotations

import os
import sys
from supabase import create_client, Client
from dotenv import load_dotenv, find_dotenv


def main() -> None:
    # Load .env so keys in env are picked up when running standalone
    load_dotenv(find_dotenv(".env") or ".env", override=False)

    supabase_url = os.getenv("SUPABASE_URL") or ""
    service_key = (
        os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_TOKEN")
        or ""
    )
    if not supabase_url:
        print("SUPABASE_URL missing in env; please paste it.")
        supabase_url = input("SUPABASE_URL: ").strip()
    if not service_key:
        print("SUPABASE_SERVICE_KEY (service_role) missing in env; please paste it.")
        service_key = input("SUPABASE_SERVICE_KEY: ").strip()
    try:
        supabase: Client = create_client(supabase_url, service_key)
    except Exception as e:
        print(f"Error initializing Supabase client: {e}")
        sys.exit(1)

    new_password = os.getenv("RESET_PASSWORD") or input("New password to set: ").strip()
    print("\nPaste user UUIDs to update. Ctrl+C to exit.\n")
    try:
        while True:
            user_id = input("User UUID: ").strip()
            if not user_id:
                continue
            try:
                supabase.auth.admin.update_user_by_id(user_id, {"password": new_password})
                print(f"✔ Updated password for user: {user_id}")
            except Exception as e:
                print(f"✖ Failed to update user {user_id}: {e}")
    except KeyboardInterrupt:
        print("\nDone.")


if __name__ == "__main__":
    main()
