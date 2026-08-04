"""Metrics, notifications, and plugins routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from security.auth import get_current_user
from system.controller import system

# ── Metrics ───────────────────────────────────────────────────────────────────

router = APIRouter()


@router.get("/live")
async def live_metrics(user: dict = Depends(get_current_user)) -> dict[str, Any]:
    return await system.monitor.get_metrics()


@router.get("/processes")
async def top_processes(n: int = 15, user: dict = Depends(get_current_user)) -> dict:
    procs = await system.monitor.get_top_processes(n)
    return {"processes": procs}
