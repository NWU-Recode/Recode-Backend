from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.common.deps import get_current_user
from app.features.notifications import repository as repo
from app.features.notifications.schemas import NotificationOut

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/me", response_model=List[NotificationOut])
async def get_my_notifications(only_unread: bool = False, limit: int = 100, current_user=Depends(get_current_user)):
    user_id = getattr(current_user, "id", None) or current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    rows = await repo.get_notifications_for_user(user_id, only_unread=only_unread, limit=limit)
    return rows


@router.patch("/{notification_id}/read", status_code=204)
async def mark_read(notification_id: str, current_user=Depends(get_current_user)):
    user_id = getattr(current_user, "id", None) or current_user.get("id")
    ok = await repo.mark_notification_read(notification_id, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Notification not found")
    return None


@router.delete("/{notification_id}", status_code=204)
async def delete_notification(notification_id: str, current_user=Depends(get_current_user)):
    user_id = getattr(current_user, "id", None) or current_user.get("id")
    ok = await repo.delete_notification(notification_id, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Notification not found")
    return None
