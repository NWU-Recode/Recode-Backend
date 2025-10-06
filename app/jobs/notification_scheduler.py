# app/jobs/notification_scheduler.py
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timedelta, timezone, time as dt_time

from app.features.notifications import repository as notif_repo

logger = logging.getLogger("notification_scheduler")


async def _sleep_until_next_utc_midnight():
    now = datetime.now(timezone.utc)
    # next midnight UTC
    tomorrow = (now + timedelta(days=1)).date()
    target = datetime.combine(tomorrow, dt_time(0, 0), tzinfo=timezone.utc)
    delta = (target - now).total_seconds()
    if delta < 0:
        delta = 0
    logger.info("Notifications scheduler sleeping until %s (UTC) -> %s seconds", target.isoformat(), delta)
    await asyncio.sleep(delta)


async def start_notification_scheduler():
    """
    Start the notifications scheduler that runs daily at midnight UTC.
    This function is intended to be started once at app startup (create_task).
    """
    logger.info("Starting notification scheduler (daily at midnight UTC)")
    while True:
        try:
            await _sleep_until_next_utc_midnight()

            # compute target = now + 24 hours; but because we run at midnight,
            # this picks challenges with due_date roughly tomorrow midnight
            target = datetime.now(timezone.utc) + timedelta(hours=24)
            window_start = target - timedelta(seconds=60)
            window_end = target + timedelta(seconds=60)

            logger.info("Running daily notification job for due_date window %s - %s", window_start.isoformat(), window_end.isoformat())

            created = await notif_repo.create_notifications_for_challenges_between(window_start, window_end)
            logger.info("Notifications created from daily job: %s", created)
        except asyncio.CancelledError:
            logger.info("Notification scheduler cancelled, exiting")
            break
        except Exception:
            logger.exception("Notification scheduler loop failed; will retry in 60s")
            await asyncio.sleep(60)
