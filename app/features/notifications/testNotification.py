# testCreateChallenge.py

import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from app.DB.session import engine
from app.features.notifications.repository import create_notifications_for_challenge


MODULE_CODE = "CMPG111"  
CHALLENGE_TITLE = "Test Challenge for Notification"
CHALLENGE_DUE_DATE = datetime.now(timezone.utc) + timedelta(days=1)  # 24h from now

async def main():
    # 1. Insert challenge into DB
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                INSERT INTO challenges (title, module_code, status, due_date, created_at)
                VALUES (:title, :module_code, 'active', :due_date, now())
                RETURNING id::text AS id
                """
            ),
            {
                "title": CHALLENGE_TITLE,
                "module_code": MODULE_CODE,
                "due_date": CHALLENGE_DUE_DATE,
            },
        )
        challenge_id = result.fetchone()[0]
        print(f"Challenge created with ID: {challenge_id}")

    # 2. Trigger notifications for enrolled users
    created_count = await create_notifications_for_challenge(challenge_id, ntype="challenge")
    print(f"Notifications created: {created_count}")

asyncio.run(main())
