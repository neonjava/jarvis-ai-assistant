"""Notifications API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from security.auth import get_current_user

router = APIRouter()


class NotificationRequest(BaseModel):
    title: str
    body: str
    source: str = "user"
    priority: str = "normal"


@router.get("/")
async def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    user: dict = Depends(get_current_user),
) -> dict:
    """List stored notifications."""
    # TODO: fetch from DB
    return {"notifications": [], "total": 0}


@router.post("/")
async def create_notification(
    req: NotificationRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    """Create and broadcast a notification."""
    from api.websocket import broadcast_notification
    await broadcast_notification(req.title, req.body, req.source)
    return {"success": True}


@router.patch("/{notification_id}/read")
async def mark_read(notification_id: str, user: dict = Depends(get_current_user)) -> dict:
    return {"success": True}
