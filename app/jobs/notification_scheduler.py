# app/jobs/notification_scheduler.py
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.features.notifications.repository import NotificationRepository

logger = logging.getLogger("notification_scheduler")


async def start_notification_scheduler():
    """
    Background scheduler that processes scheduled notifications every minute.
    """
    logger.info("Notification scheduler started")
    while True:
        try:
            now = datetime.now(timezone.utc)
            window_start = now
            window_end = now + timedelta(seconds=60)  # look 1 minute ahead

            created_count = await NotificationRepository.process_scheduled_notifications_between(
                window_start, window_end
            )
            logger.info(f"Scheduled notifications processed: {created_count}")

            # Sleep until the next minute
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            logger.info("Notification scheduler cancelled")
            break
        except Exception as e:
            logger.exception(f"Notification scheduler error: {e}, retrying in 60s")
            await asyncio.sleep(60)


# Optional: helper to run scheduler standalone for testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_notification_scheduler())
