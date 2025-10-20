#app\features\notifications\scheduler.py
import asyncio
import logging
from datetime import datetime, timezone

from app.features.notifications.service import NotificationService

logger = logging.getLogger(__name__)

async def notification_scheduler():
    """Runs every 10 minutes to send challenge notifications."""
    while True:
        try:
            logger.info(f"🔄 Notification scheduler tick at {datetime.now(timezone.utc)}")
            await NotificationService.notify_challenge_open()
            await NotificationService.notify_challenge_due()
        except Exception as e:
            logger.error(f"Scheduler error: {e}")

        await asyncio.sleep(600)  # every 10 minutes
