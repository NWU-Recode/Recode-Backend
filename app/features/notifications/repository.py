# app/features/notifications/repository.py
from __future__ import annotations
import asyncio
import logging
import smtplib
from email.message import EmailMessage
from typing import Any, Dict, List, Optional
from datetime import datetime

from sqlalchemy import text
from app.DB.session import engine
from app.features.notifications.schemas import NotificationOut

logger = logging.getLogger(__name__)


# -------------------------------
# 🔹 SYNC HELPERS (DB OPERATIONS)
# -------------------------------

def _sync_fetch_challenge_by_id(challenge_id: str) -> Optional[Dict[str, Any]]:
    with engine.connect() as conn:
        r = conn.execute(
            text("SELECT id::text AS id, title, module_code, due_date FROM challenges WHERE id = :id"),
            {"id": challenge_id},
        )
        row = r.fetchone()
        return dict(row._mapping) if row else None


def _sync_fetch_challenges_between(start: datetime, end: datetime) -> List[Dict[str, Any]]:
    with engine.connect() as conn:
        res = conn.execute(
            text(
                """
                SELECT id::text AS id, title, module_code, due_date
                FROM challenges
                WHERE status = 'active' AND due_date BETWEEN :start AND :end
                """
            ),
            {"start": start, "end": end},
        )
        return [dict(r._mapping) for r in res]


def _sync_get_module_id_by_code(module_code: str) -> Optional[str]:
    with engine.connect() as conn:
        r = conn.execute(
            text("SELECT id::text AS id FROM modules WHERE code = :code LIMIT 1"),
            {"code": module_code},
        )
        row = r.fetchone()
        return row[0] if row else None


def _sync_get_enrolled_student_ids(module_id: str) -> List[int]:
    with engine.connect() as conn:
        res = conn.execute(
            text(
                """
                SELECT student_id
                FROM enrolments
                WHERE module_id = :module_id AND status = 'active' AND student_id IS NOT NULL
                """
            ),
            {"module_id": module_id},
        )
        return [int(r[0]) for r in res]


def _sync_insert_notification_if_not_exists(
    user_id: int,
    title: str,
    message: str,
    ntype: str,
    link_url: Optional[str],
    expires_at: Optional[datetime],
) -> bool:
    """Insert a notification if no duplicate in last 48h for same user/type/link."""
    with engine.begin() as conn:
        dup = conn.execute(
            text(
                """
                SELECT 1 FROM notification
                WHERE user_id = :user_id AND type = :type AND link_url = :link_url
                  AND created_at >= now() - interval '48 hours'
                LIMIT 1
                """
            ),
            {"user_id": user_id, "type": ntype, "link_url": link_url},
        ).fetchone()
        if dup:
            return False

        conn.execute(
            text(
                """
                INSERT INTO notification
                    (user_id, title, message, type, priority, link_url, expires_at, created_at, read)
                VALUES
                    (:user_id, :title, :message, :type, :priority, :link_url, :expires_at, now(), false)
                """
            ),
            {
                "user_id": user_id,
                "title": title,
                "message": message,
                "type": ntype,
                "priority": 1,
                "link_url": link_url,
                "expires_at": expires_at,
            },
        )
        return True


def _sync_get_user_email(user_id: int) -> Optional[Dict[str, Any]]:
    with engine.connect() as conn:
        r = conn.execute(
            text("SELECT email, full_name FROM profiles WHERE id = :id"),
            {"id": user_id},
        ).fetchone()
        return dict(r._mapping) if r else None


def _sync_get_notifications_for_user(user_id: int, only_unread: bool = False, limit: int = 100):
    """Fetch notifications for a user."""
    with engine.connect() as conn:
        q = """
            SELECT id::text AS id, user_id, title, message, type, priority,
                   link_url, expires_at, created_at, read
            FROM notification
            WHERE user_id = :user_id
        """
        if only_unread:
            q += " AND read = false"
        q += " ORDER BY created_at DESC LIMIT :limit"

        res = conn.execute(text(q), {"user_id": user_id, "limit": limit})
        return [NotificationOut(**dict(r._mapping)) for r in res]


def _sync_mark_notification_read(notification_id: int, user_id: int) -> bool:
    with engine.begin() as conn:
        r = conn.execute(
            text("UPDATE notification SET read = true WHERE id = :id AND user_id = :user_id RETURNING id"),
            {"id": notification_id, "user_id": user_id},
        ).fetchone()
        return bool(r)


def _sync_delete_notification(notification_id: int, user_id: int) -> bool:
    with engine.begin() as conn:
        r = conn.execute(
            text("DELETE FROM notification WHERE id = :id AND user_id = :user_id RETURNING id"),
            {"id": notification_id, "user_id": user_id},
        ).fetchone()
        return bool(r)


# -------------------------------
# 🔹 ASYNC WRAPPERS
# -------------------------------

async def fetch_challenge(challenge_id: str) -> Optional[Dict[str, Any]]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_fetch_challenge_by_id, challenge_id)


async def get_challenges_ending_between(start: datetime, end: datetime) -> List[Dict[str, Any]]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_fetch_challenges_between, start, end)


async def create_notifications_for_challenge(challenge_id: str, ntype: str = "deadline") -> int:
    """Create notifications for all enrolled students in a challenge."""
    loop = asyncio.get_running_loop()
    challenge = await fetch_challenge(challenge_id)
    if not challenge:
        return 0

    module_code = challenge.get("module_code")
    if not module_code:
        logger.warning("Challenge %s has no module_code; skipping", challenge_id)
        return 0

    module_id = await loop.run_in_executor(None, _sync_get_module_id_by_code, module_code)
    if not module_id:
        logger.warning("No module found for code %s (challenge %s)", module_code, challenge_id)
        return 0

    student_ids = await loop.run_in_executor(None, _sync_get_enrolled_student_ids, module_id)
    if not student_ids:
        return 0

    title = "Challenge Ending Soon" if ntype == "deadline" else "New Challenge Available"
    message = f"{challenge.get('title')} ends in 24 hours" if ntype == "deadline" else f"{challenge.get('title')} is now live"
    link = f"/challenges/{challenge_id}"

    created = 0
    for sid in student_ids:
        ok = await loop.run_in_executor(
            None, _sync_insert_notification_if_not_exists,
            sid, title, message, ntype, link, challenge.get("due_date")
        )
        if ok:
            created += 1
    return created


async def get_notifications_for_user(user_id: int, only_unread: bool = False, limit: int = 100):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_get_notifications_for_user, user_id, only_unread, limit)


async def mark_notification_read(notification_id: int, user_id: int):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_mark_notification_read, notification_id, user_id)


async def delete_notification(notification_id: int, user_id: int):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_delete_notification, notification_id, user_id)
