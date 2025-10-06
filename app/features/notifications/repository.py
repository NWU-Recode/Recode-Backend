# app/features/notifications/repository.py
from __future__ import annotations
import asyncio
import logging
import smtplib
from email.message import EmailMessage
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta

from sqlalchemy import text
from app.DB.session import engine  

logger = logging.getLogger(__name__)



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
        r = conn.execute(text("SELECT id::text AS id FROM modules WHERE code = :code LIMIT 1"), {"code": module_code})
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
        # cast to ints if necessary
        return [int(r[0]) for r in res]


def _sync_insert_notification_if_not_exists(user_id: int, title: str, message: str, ntype: str, link_url: Optional[str], expires_at: Optional[datetime]) -> bool:
    """
    Inserts a notification if a similar notification hasn't been created in the last 48 hours for the same user/type/link.
    Returns True if inserted, False if skipped due to duplicate.
    """
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
                INSERT INTO notification (user_id, title, message, type, priority, link_url, expires_at, created_at, read)
                VALUES (:user_id, :title, :message, :type, :priority, :link_url, :expires_at, now(), false)
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
        r = conn.execute(text("SELECT email, full_name FROM profiles WHERE id = :id"), {"id": user_id}).fetchone()
        if not r:
            return None
        return dict(r._mapping)


def _sync_mark_notification_read(notification_id: str, user_id: int) -> bool:
    with engine.begin() as conn:
        r = conn.execute(
            text("UPDATE notification SET read = true WHERE id = :id AND user_id = :user_id RETURNING id"),
            {"id": notification_id, "user_id": user_id},
        ).fetchone()
        return bool(r)


def _sync_delete_notification(notification_id: str, user_id: int) -> bool:
    with engine.begin() as conn:
        r = conn.execute(
            text("DELETE FROM notification WHERE id = :id AND user_id = :user_id RETURNING id"),
            {"id": notification_id, "user_id": user_id},
        ).fetchone()
        return bool(r)


def _sync_get_notifications_for_user(user_id: int, only_unread: bool = False, limit: int = 100) -> List[Dict[str, Any]]:
    with engine.connect() as conn:
        q = "SELECT id::text AS id, user_id, title, message, type, priority, link_url, expires_at, created_at, read FROM notification WHERE user_id = :user_id"
        if only_unread:
            q += " AND read = false"
        q += " ORDER BY created_at DESC LIMIT :limit"
        res = conn.execute(text(q), {"user_id": user_id, "limit": limit})
        return [dict(r._mapping) for r in res]



async def fetch_challenge(challenge_id: str) -> Optional[Dict[str, Any]]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_fetch_challenge_by_id, challenge_id)


async def get_challenges_ending_between(start: datetime, end: datetime) -> List[Dict[str, Any]]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_fetch_challenges_between, start, end)


async def create_notifications_for_challenge(challenge_id: str, ntype: str = "deadline") -> int:
    """
    For a given challenge id: create notifications for enrolled students.
    Returns number of notifications created.
    This function is safe to call from background tasks.
    """
    loop = asyncio.get_running_loop()
    challenge = await fetch_challenge(challenge_id)
    if not challenge:
        return 0

    module_code = challenge.get("module_code")
    if not module_code:
        logger.warning("Challenge %s has no module_code; skipping notifications", challenge_id)
        return 0

    # get module id then students
    module_id = await loop.run_in_executor(None, _sync_get_module_id_by_code, module_code)
    if not module_id:
        logger.warning("No module matching code %s (challenge %s); skipping", module_code, challenge_id)
        return 0

    student_ids = await loop.run_in_executor(None, _sync_get_enrolled_student_ids, module_id)
    if not student_ids:
        logger.debug("No enrolled students for module %s (challenge %s)", module_code, challenge_id)
        return 0

    title = "Challenge Ending Soon" if ntype == "deadline" else "New Challenge Available"
    message = f"{challenge.get('title')} ends in 24 hours" if ntype == "deadline" else f"{challenge.get('title')} is now live"
    link = f"/challenges/{challenge_id}"

    created = 0
    for sid in student_ids:
        ok = await loop.run_in_executor(None, _sync_insert_notification_if_not_exists, sid, title, message, ntype, link, challenge.get("due_date"))
        if ok:
            created += 1

            # optional email send: look for SMTP env in runtime, send mail if found
            # We keep email sending synchronous in executor to avoid extra async SMTP deps
            from os import getenv

            smtp_user = getenv("SMTP_USER")
            smtp_host = getenv("SMTP_HOST")
            smtp_port = int(getenv("SMTP_PORT") or 0) if getenv("SMTP_PORT") else None
            smtp_pass = getenv("SMTP_PASS")
            if smtp_user and smtp_pass and smtp_host and smtp_port:
                recipient = loop.run_in_executor(None, _sync_get_user_email, sid)
                user_info = await recipient
                if user_info and user_info.get("email"):
                    # fire-and-forget email send
                    asyncio.create_task(_async_send_email(smtp_host, smtp_port, smtp_user, smtp_pass, user_info["email"], title, message))

    return created


async def create_notifications_for_challenges_between(start: datetime, end: datetime) -> int:
    """
    Create notifications for all active challenges whose due_date is between start and end.
    Returns total number of notifications created.
    """
    items = await get_challenges_ending_between(start, end)
    total = 0
    for c in items:
        total += await create_notifications_for_challenge(c["id"], ntype="deadline")
    return total


async def get_notifications_for_user(user_id: int, only_unread: bool = False, limit: int = 100) -> List[Dict[str, Any]]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_get_notifications_for_user, user_id, only_unread, limit)


async def mark_notification_read(notification_id: str, user_id: int) -> bool:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_mark_notification_read, notification_id, user_id)


async def delete_notification(notification_id: str, user_id: int) -> bool:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_delete_notification, notification_id, user_id)


# -----------------------
# Email (runs in executor)
# -----------------------
def _send_email_sync(smtp_host: str, smtp_port: int, smtp_user: str, smtp_pass: str, to_email: str, subject: str, body: str):
    try:
        msg = EmailMessage()
        msg["From"] = smtp_user
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)

        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as s:
            s.ehlo()
            s.starttls()
            s.login(smtp_user, smtp_pass)
            s.send_message(msg)
    except Exception:
        logger.exception("Failed to send notification email to %s", to_email)


async def _async_send_email(smtp_host: str, smtp_port: int, smtp_user: str, smtp_pass: str, to_email: str, subject: str, body: str):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _send_email_sync, smtp_host, smtp_port, smtp_user, smtp_pass, to_email, subject, body)
