"""Plugins API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from plugins.sdk import plugin_registry
from security.auth import get_current_user, require_admin

router = APIRouter()


class PluginCommandRequest(BaseModel):
    command: str
    params: dict = {}


@router.get("/")
async def list_plugins(user: dict = Depends(get_current_user)) -> dict:
    return {"plugins": plugin_registry.list_plugins()}


@router.get("/commands")
async def list_commands(user: dict = Depends(get_current_user)) -> dict:
    return {"commands": plugin_registry.get_all_commands()}


@router.post("/{plugin_name}/command")
async def execute_plugin_command(
    plugin_name: str,
    req: PluginCommandRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    result = await plugin_registry.execute_command(req.command, **req.params)
    if result is None:
        return {"success": False, "error": "Command not found"}
    return {"success": True, "result": result}
