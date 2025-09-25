#!/usr/bin/env python
"""Confirm Supabase user emails via service role key from app config.

Usage: python scripts/confirm_supabase_email.py

- Loads Supabase credentials via app.Core.config.get_settings().
- Prompts for a Supabase user UUID; Ctrl+C exits.
"""
from __future__ import annotations

import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union
import argparse

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from app.Core.config import get_settings
except ImportError:  # pragma: no cover - safety for misconfigured PYTHONPATH
    print("Could not import app.Core.config.get_settings. Ensure you run this from the project root or set PYTHONPATH appropriately.")
    sys.exit(1)


def _exit(msg: str, code: int = 1) -> None:
    print(msg)
    sys.exit(code)


def _load_supabase_config() -> tuple[str, str]:
    settings = get_settings()
    # Prefer the explicit service role key names, fall back to other names
    url = getattr(settings, "SUPABASE_URL", None) or getattr(settings, "supabase_url", "")
    service_key = (
        getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "")
        or getattr(settings, "SUPABASE_SERVICE_KEY", "")
        or getattr(settings, "supabase_service_role_key", "")
        or getattr(settings, "supabase_service_key", "")
    )
    # Don't fall back to anon key for the service role key — we must use a
    # privileged key to confirm emails. If you only have anon key, bail out.
    if not url:
        _exit("Supabase URL missing; check your configuration/env settings.")
    if not service_key:
        _exit("Supabase service role key missing; set SUPABASE_SERVICE_ROLE_KEY or SUPABASE_SERVICE_KEY. Do NOT use the anon key.")
    return url.rstrip("/"), service_key


def _confirm_email(user_uuid: str, base_endpoint: str, service_key: str) -> bool:
    """Perform the Supabase admin update to mark an email confirmed.

    Returns True on success, False otherwise.
    """
    iso_timestamp = datetime.now(timezone.utc).isoformat()
    payload = {
        "email_confirmed_at": iso_timestamp,
        "confirmed_at": iso_timestamp,
        "last_sign_in_at": iso_timestamp,
    }
    headers = {
        "Authorization": f"Bearer {service_key}",
        "apikey": service_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    methods_to_try = ["PATCH", "PUT", "POST"]
    response = None
    succeeded_method: Optional[str] = None
    for method in methods_to_try:
        try:
            # Use requests.request so we can switch method dynamically
            response = requests.request(method, base_endpoint + user_uuid, headers=headers, json=payload, timeout=15)
        except requests.RequestException as exc:
            print(f"Request failed ({method}): {exc}\n")
            continue

        if response.status_code == 200:
            succeeded_method = method
            break
        # If method not allowed, try next method
        if response.status_code == 405:
            allow = response.headers.get("Allow")
            print(f"{method} returned 405 Method Not Allowed. Allow: {allow}")
            # try next method
            continue
        # For other statuses, no need to try alternate methods
        break

    if response is None:
        print("All requests failed to send")
        return False

    if response.status_code == 200:
        if succeeded_method:
            print(f"Request succeeded using {succeeded_method}")
        try:
            data = response.json()
            confirmed_at = data.get("confirmed_at")
            email_confirmed_at = data.get("email_confirmed_at")
        except ValueError:
            confirmed_at = email_confirmed_at = None
        print(f"[OK] Email confirmed for user {user_uuid}")
        if confirmed_at or email_confirmed_at:
            print(f"    confirmed_at: {confirmed_at} | email_confirmed_at: {email_confirmed_at}")
        print()
        return True
    else:
        # Print full response for debugging
        print(f"[WARN] Failed to confirm email ({response.status_code})")
        try:
            print("Response JSON:", response.json())
        except ValueError:
            print("Response text:", response.text)
        print("Response headers:", dict(response.headers))
        if response.status_code == 404:
            print("    (Ensure you provided the auth.users UUID, not the profile ID.)")
        print()
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Confirm Supabase user emails via service role key from app config")
    parser.add_argument("--user", "-u", help="Supabase user UUID to confirm (one-shot)")
    parser.add_argument("--yes", "-y", action="store_true", help="Don't prompt for confirmation when using --user")
    parser.add_argument("--dry-run", action="store_true", help="Print the request that would be sent and exit")
    parser.add_argument("--verify", action="store_true", help="GET the user before and after the update to verify persisted fields")
    args = parser.parse_args()

    supabase_url, service_key = _load_supabase_config()
    base_endpoint = f"{supabase_url}/auth/v1/admin/users/"

    print(f"Supabase URL: {supabase_url}")
    if args.user:
        print(f"One-shot mode: will confirm user {args.user}")
    else:
        print("Ready to confirm emails interactively. Press Ctrl+C to quit.\n")

    def _handle_sigint(_sig, _frame):
        print("\nGoodbye!")
        sys.exit(0)

    signal.signal(signal.SIGINT, _handle_sigint)

    # One-shot non-interactive mode
    if args.user:
        user_uuid = args.user.strip()
        if not user_uuid:
            _exit("--user provided but empty UUID", 2)
        if not args.yes:
            confirm = input(f"Confirm email for user {user_uuid}? [y/N]: ").strip().lower()
            if confirm not in ("y", "yes"):
                print("Aborted by user.")
                return
        if args.dry_run:
            print("DRY RUN: would PATCH:")
            iso_timestamp = datetime.now(timezone.utc).isoformat()
            print({
                "email_confirmed_at": iso_timestamp,
                "confirmed_at": iso_timestamp,
                "last_sign_in_at": iso_timestamp,
            })
            print("headers:", {"Authorization": f"Bearer {service_key}", "apikey": service_key})
            return
        if args.verify:
            # GET before
            try:
                before = requests.get(base_endpoint + user_uuid, headers={"Authorization": f"Bearer {service_key}", "apikey": service_key}, timeout=10)
                print("Before GET status:", before.status_code)
                try:
                    print("Before JSON:", before.json())
                except ValueError:
                    print("Before text:", before.text)
            except requests.RequestException as exc:
                print("Before GET failed:", exc)
        _confirm_email(user_uuid, base_endpoint, service_key)
        if args.verify:
            # GET after
            try:
                after = requests.get(base_endpoint + user_uuid, headers={"Authorization": f"Bearer {service_key}", "apikey": service_key}, timeout=10)
                print("After GET status:", after.status_code)
                try:
                    print("After JSON:", after.json())
                except ValueError:
                    print("After text:", after.text)
            except requests.RequestException as exc:
                print("After GET failed:", exc)
        return
        return

    # Interactive mode
    while True:
        user_uuid = input("Enter Supabase user UUID: ").strip()
        if not user_uuid:
            continue

        _confirm_email(user_uuid, base_endpoint, service_key)


if __name__ == "__main__":
    main()



