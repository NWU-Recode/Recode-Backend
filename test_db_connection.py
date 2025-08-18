"""Simple script to verify Supabase connectivity.

Run:  python test_db_connection.py
Exits with code 0 on success, non-zero on failure.
"""

import asyncio
from app.DB.supabase import get_supabase


async def main() -> int:
    try:
        client = await get_supabase()
        # Test basic connectivity with a simple query
        result = await client.table("users").select("id").limit(1).execute()
        print(result)
        print("Supabase connection OK")
        return 0
    except Exception as e:
        print(f"Supabase connection FAILED: {e}")
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(asyncio.run(main()))
