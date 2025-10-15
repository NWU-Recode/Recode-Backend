#app\api\notifications_schedule.py
from __future__ import annotations
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from app.features.notifications.repository import NotificationRepository as notif_repo


router = APIRouter(prefix="/notifications/schedule", tags=["NotificationSchedule"])


class ScheduleItem(BaseModel):
    notification_type: str
    notification_time: datetime
    sent: Optional[bool] = False
    id: Optional[str] = None


@router.get("/{challenge_id}", response_model=List[ScheduleItem])
async def get_schedule(challenge_id: str):
    rows = await notif_repo.get_schedule_for_challenge(challenge_id)
    if not rows:
        raise HTTPException(status_code=404, detail="No schedule found for challenge")
    # ensure timezone aware datetimes returned as UTC
    return rows


@router.post("/test/{challenge_id}")
async def test_fire_notifications(challenge_id: str, background_tasks: BackgroundTasks, as_of: Optional[datetime] = Query(None, description="If provided, only notifications with notification_time <= as_of will be fired")):
    """
    Simulate firing scheduled notifications for this challenge.
    If `as_of` provided, only schedules <= as_of will be fired. Otherwise fires all schedule types for challenge.
    """
    schedule = await notif_repo.get_schedule_for_challenge(challenge_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="No schedule found for challenge")

    to_fire = []
    if as_of:
        # convert to utc
        as_of_utc = as_of.astimezone(timezone.utc)
        for item in schedule:
            if item["notification_time"] <= as_of_utc:
                to_fire.append(item["notification_type"])
    else:
        to_fire = [item["notification_type"] for item in schedule]

    if not to_fire:
        return {"status": "ok", "message": "No notifications due at specified time.", "fired": 0}

    created_total = 0
    for ntype in to_fire:
        mapped = "start" if ntype == "start" else "deadline"
        # call and await so Swagger shows result when done
        created_total += await notif_repo.create_notifications_for_challenge(challenge_id, ntype=mapped)

    return {"status": "ok", "message": f"Simulated notifications fired for challenge {challenge_id}", "fired": created_total}


@router.post("/recompute/{challenge_id}")
async def recompute_schedule(challenge_id: str):
    try:
        await notif_repo.recompute_schedule(challenge_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Challenge not found")
    return {"status": "ok", "message": "Recomputed notification schedule for challenge", "challenge_id": challenge_id}
