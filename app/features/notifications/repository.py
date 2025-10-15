# app/features/notifications/repository.py
from __future__ import annotations
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from sqlalchemy import text
from app.DB.session import engine  # adjust import path to your setup

logger = logging.getLogger(__name__)


class NotificationRepository:
    @classmethod
    async def create_notification(
        cls,
        user_id: int,
        title: str,
        message: str,
        type_: str = "general",
        priority: int = 1,
        link_url: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        loop = asyncio.get_running_loop()

        def _insert():
            with engine.begin() as conn:
                result = conn.execute(
                    text("""
                        INSERT INTO notification (user_id, title, message, type, priority, link_url, expires_at)
                        VALUES (:user_id, :title, :message, :type, :priority, :link_url, :expires_at)
                        RETURNING *
                    """),
                    dict(
                        user_id=user_id,
                        title=title,
                        message=message,
                        type=type_,
                        priority=priority,
                        link_url=link_url,
                        expires_at=expires_at,
                    ),
                ).fetchone()
                return dict(result._mapping)

        return await loop.run_in_executor(None, _insert)

    @classmethod
    async def get_unread(cls, user_id: int) -> List[Dict[str, Any]]:
        loop = asyncio.get_running_loop()

        def _fetch():
            with engine.connect() as conn:
                rows = conn.execute(
                    text("""
                        SELECT * FROM notification
                        WHERE user_id = :user_id AND read = false
                        ORDER BY created_at DESC
                    """),
                    {"user_id": user_id},
                ).fetchall()
                return [dict(r._mapping) for r in rows]

        return await loop.run_in_executor(None, _fetch)

    @classmethod
    async def mark_as_read(cls, notification_id: str):
        loop = asyncio.get_running_loop()

        def _update():
            with engine.begin() as conn:
                conn.execute(
                    text("UPDATE notification SET read = true WHERE id = :id"),
                    {"id": notification_id},
                )

        await loop.run_in_executor(None, _update)

    @classmethod
    async def user_has_notification(cls, user_id: int, title: str) -> bool:
        loop = asyncio.get_running_loop()

        def _check():
            with engine.connect() as conn:
                row = conn.execute(
                    text("""
                        SELECT 1 FROM notification
                        WHERE user_id = :user_id AND title = :title
                        LIMIT 1
                    """),
                    {"user_id": user_id, "title": title},
                ).fetchone()
                return row is not None

        return await loop.run_in_executor(None, _check)

    @classmethod
    async def create_notifications_for_challenge(cls, challenge_id: str, ntype: str = "general") -> int:
        """
        Placeholder method to create notifications for a challenge.
        Returns the number of notifications created.
        """
        # Here you would fetch users who need this challenge notification
        # For demo, just log and return 1
        logger.info(f"Creating notifications for challenge {challenge_id} of type {ntype}")
        return 1

    @classmethod
    async def process_scheduled_notifications_between(cls, window_start: datetime, window_end: datetime) -> int:
        """
        Process scheduled notifications whose times fall within the given window.
        Marks them as sent and returns the total number created.
        """
        loop = asyncio.get_running_loop()

        def _process():
            total_created = 0
            with engine.begin() as conn:
                # Fetch scheduled notifications
                rows = conn.execute(
                    text("""
                        SELECT challenge_id, notification_type
                        FROM notification_schedule
                        WHERE notification_time BETWEEN :start AND :end
                          AND sent = FALSE
                    """),
                    {"start": window_start, "end": window_end}
                ).fetchall()

                for row in rows:
                    challenge_id = row["challenge_id"]
                    ntype = row["notification_type"]

                    # Create notifications for this challenge
                    created = asyncio.run(cls.create_notifications_for_challenge(challenge_id, ntype))
                    total_created += created

                    # Mark as sent
                    conn.execute(
                        text("""
                            UPDATE notification_schedule
                            SET sent = TRUE
                            WHERE challenge_id = :cid AND notification_type = :ntype
                        """),
                        {"cid": challenge_id, "ntype": ntype}
                    )

            return total_created

        return await loop.run_in_executor(None, _process)
