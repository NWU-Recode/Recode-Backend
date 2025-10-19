import asyncio
import uuid
from datetime import datetime, timezone
from sqlalchemy import text
from app.DB.session import engine

MODULE_CODE = "CMPG111"
MESSAGE_TITLE = "Forced Test Challenge Notification"
MESSAGE_BODY = "This notification is forced for testing purposes."

async def force_notifications():
    with engine.begin() as conn:
        students = conn.execute(
            text(
                "SELECT student_id FROM enrolments e "
                "JOIN modules m ON e.module_id = m.id "
                "WHERE m.code = :module_code"
            ),
            {"module_code": MODULE_CODE}
        ).fetchall()

        for s in students:
            conn.execute(
                text(
                    "INSERT INTO notification (user_id, title, message, type, priority, link_url, created_at, read) "
                    "VALUES (:user_id, :title, :message, 'challenge', 1, :link_url, now(), false) "
                    "ON CONFLICT (user_id, link_url) DO NOTHING"
                ),
                {
                    "user_id": s.student_id,
                    "title": MESSAGE_TITLE,
                    "message": MESSAGE_BODY,
                    "link_url": f"/challenges/test-challenge-{uuid.uuid4().hex[:6]}"
                }
            )
            print(f"[INFO] Notification inserted for student_id={s.student_id}")

if __name__ == "__main__":
    asyncio.run(force_notifications())
