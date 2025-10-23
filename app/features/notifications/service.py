#app\features\notifications\service.py
import asyncio
import logging
import smtplib
from email.message import EmailMessage
from datetime import datetime, timezone, timedelta
import os

from sqlalchemy import text
from app.db.database import engine
from app.features.notifications.repository import NotificationRepository

logger = logging.getLogger(__name__)


class NotificationService:
    SMTP_HOST = os.getenv("SMTP_HOST")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER")
    SMTP_PASS = os.getenv("SMTP_PASS")
    FROM_EMAIL = os.getenv("FROM_EMAIL", "no-reply@clearvue.com")

    @classmethod
    async def send_email(cls, to_email: str, subject: str, body: str):
        loop = asyncio.get_running_loop()

        def _send():
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = cls.FROM_EMAIL
            msg["To"] = to_email
            msg.set_content(body)

            with smtplib.SMTP(cls.SMTP_HOST, cls.SMTP_PORT) as smtp:
                smtp.starttls()
                smtp.login(cls.SMTP_USER, cls.SMTP_PASS)
                smtp.send_message(msg)

        try:
            await loop.run_in_executor(None, _send)
            logger.info(f"✅ Sent email to {to_email}")
        except Exception as e:
            logger.error(f"❌ Email send failed: {e}")

    @classmethod
    async def notify_challenge_open(cls):
        """Notify users when challenges become active"""
        loop = asyncio.get_running_loop()
        now = datetime.now(timezone.utc)

        def _fetch_open():
            with engine.connect() as conn:
                rows = conn.execute(
                    text("""
                        SELECT c.id, c.title, e.student_id, p.email
                        FROM challenges c
                        JOIN enrolments e ON e.module_id = c.module_code::uuid
                        JOIN profiles p ON p.id = e.student_id
                        WHERE c.release_date <= now() AND c.status = 'active'
                    """)
                ).fetchall()
                return [dict(r._mapping) for r in rows]

        challenges = await loop.run_in_executor(None, _fetch_open)

        for ch in challenges:
            title = f"Challenge Open: {ch['title']}"
            message = f"A new challenge '{ch['title']}' is now available. Start now!"

            if not await NotificationRepository.user_has_notification(ch["student_id"], title):
                await NotificationRepository.create_notification(
                    ch["student_id"],
                    title,
                    message,
                    type_="challenge_open",
                    priority=2,
                    link_url=f"/challenges/{ch['id']}",
                )
                await cls.send_email(ch["email"], title, message)

    @classmethod
    async def notify_challenge_due(cls):
        """Notify users 24h before challenge due date"""
        loop = asyncio.get_running_loop()
        now = datetime.now(timezone.utc)
        soon = now + timedelta(hours=24)

        def _fetch_due():
            with engine.connect() as conn:
                rows = conn.execute(
                    text("""
                        SELECT c.id, c.title, e.student_id, p.email
                        FROM challenges c
                        JOIN enrolments e ON e.module_id = c.module_code::uuid
                        JOIN profiles p ON p.id = e.student_id
                        WHERE c.due_date BETWEEN now() AND (now() + interval '24 hours')
                          AND c.status = 'active'
                    """)
                ).fetchall()
                return [dict(r._mapping) for r in rows]

        challenges = await loop.run_in_executor(None, _fetch_due)

        for ch in challenges:
            title = f"Challenge Due Soon: {ch['title']}"
            message = f"Reminder: The challenge '{ch['title']}' is due within 24 hours."

            if not await NotificationRepository.user_has_notification(ch["student_id"], title):
                await NotificationRepository.create_notification(
                    ch["student_id"],
                    title,
                    message,
                    type_="challenge_due",
                    priority=3,
                    link_url=f"/challenges/{ch['id']}",
                )
                await cls.send_email(ch["email"], title, message)
import asyncio
import logging
import smtplib
from email.message import EmailMessage
from datetime import datetime, timezone, timedelta
import os

from sqlalchemy import text
from app.DB.session import engine
from app.features.notifications.repository import NotificationRepository

logger = logging.getLogger(__name__)


class NotificationService:
    SMTP_HOST = os.getenv("SMTP_HOST")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER")
    SMTP_PASS = os.getenv("SMTP_PASS")
    FROM_EMAIL = os.getenv("FROM_EMAIL", "no-reply@clearvue.com")

    @classmethod
    async def send_email(cls, to_email: str, subject: str, body: str):
        loop = asyncio.get_running_loop()

        def _send():
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = cls.FROM_EMAIL
            msg["To"] = to_email
            msg.set_content(body)

            with smtplib.SMTP(cls.SMTP_HOST, cls.SMTP_PORT) as smtp:
                smtp.starttls()
                smtp.login(cls.SMTP_USER, cls.SMTP_PASS)
                smtp.send_message(msg)

        try:
            await loop.run_in_executor(None, _send)
            logger.info(f"✅ Sent email to {to_email}")
        except Exception as e:
            logger.error(f"❌ Email send failed: {e}")

    @classmethod
    async def notify_challenge_open(cls):
        """Notify users when challenges become active"""
        loop = asyncio.get_running_loop()
        now = datetime.now(timezone.utc)

        def _fetch_open():
            with engine.connect() as conn:
                rows = conn.execute(
                    text("""
                        SELECT c.id, c.title, e.student_id, p.email
                        FROM challenges c
                        JOIN enrolments e ON e.module_id = c.module_code::uuid
                        JOIN profiles p ON p.id = e.student_id
                        WHERE c.release_date <= now() AND c.status = 'active'
                    """)
                ).fetchall()
                return [dict(r._mapping) for r in rows]

        challenges = await loop.run_in_executor(None, _fetch_open)

        for ch in challenges:
            title = f"Challenge Open: {ch['title']}"
            message = f"A new challenge '{ch['title']}' is now available. Start now!"

            if not await NotificationRepository.user_has_notification(ch["student_id"], title):
                await NotificationRepository.create_notification(
                    ch["student_id"],
                    title,
                    message,
                    type_="challenge_open",
                    priority=2,
                    link_url=f"/challenges/{ch['id']}",
                )
                await cls.send_email(ch["email"], title, message)

    @classmethod
    async def notify_challenge_due(cls):
        """Notify users 24h before challenge due date"""
        loop = asyncio.get_running_loop()
        now = datetime.now(timezone.utc)
        soon = now + timedelta(hours=24)

        def _fetch_due():
            with engine.connect() as conn:
                rows = conn.execute(
                    text("""
                        SELECT c.id, c.title, e.student_id, p.email
                        FROM challenges c
                        JOIN enrolments e ON e.module_id = c.module_code::uuid
                        JOIN profiles p ON p.id = e.student_id
                        WHERE c.due_date BETWEEN now() AND (now() + interval '24 hours')
                          AND c.status = 'active'
                    """)
                ).fetchall()
                return [dict(r._mapping) for r in rows]

        challenges = await loop.run_in_executor(None, _fetch_due)

        for ch in challenges:
            title = f"Challenge Due Soon: {ch['title']}"
            message = f"Reminder: The challenge '{ch['title']}' is due within 24 hours."

            if not await NotificationRepository.user_has_notification(ch["student_id"], title):
                await NotificationRepository.create_notification(
                    ch["student_id"],
                    title,
                    message,
                    type_="challenge_due",
                    priority=3,
                    link_url=f"/challenges/{ch['id']}",
                )
                await cls.send_email(ch["email"], title, message)
