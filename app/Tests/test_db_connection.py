"""Simple script to verify database connectivity using configured DATABASE_URL.

Run:  python test_db_connection.py
Exits with code 0 on success, non-zero on failure.
"""

from sqlalchemy import text
from app.DB.session import SessionLocal


def main() -> int:
    try:
        with SessionLocal() as session:
            result = session.execute(text("SELECT 1")).scalar()
        if result == 1:
            print("DB connection OK (SELECT 1 returned 1)")
            return 0
        print(f"Unexpected result: {result}")
        return 2
    except Exception as e:
        print(f"DB connection FAILED: {e}")
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
