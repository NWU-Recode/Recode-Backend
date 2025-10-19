#app\features\notifications\endpoints.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.common.deps import get_current_user
from app.features.notifications import repository as repo
from app.features.notifications.schemas import NotificationOut

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.get("/{user_id}")
async def get_unread_notifications(user_id: int):
    data = await NotificationRepository.get_unread(user_id)
    return {"count": len(data), "notifications": data}

@router.post("/{notification_id}/read")
async def mark_notification_read(notification_id: str):
    await NotificationRepository.mark_as_read(notification_id)
    return {"status": "ok"}
