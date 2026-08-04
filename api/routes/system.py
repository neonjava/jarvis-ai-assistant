"""System control API routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from system.controller import system
from security.auth import get_current_user, is_dangerous

router = APIRouter()


class VolumeRequest(BaseModel):
    level: int


class BrightnessRequest(BaseModel):
    level: int


class AppRequest(BaseModel):
    name: str


class ShellRequest(BaseModel):
    command: str
    confirm: bool = False


class FileRequest(BaseModel):
    path: str
    content: str = ""
    recursive: bool = False


class MoveRequest(BaseModel):
    src: str
    dst: str


class TypeRequest(BaseModel):
    text: str


class ClipboardRequest(BaseModel):
    text: str


@router.get("/status")
async def system_status(user: dict = Depends(get_current_user)) -> dict[str, Any]:
    return await system.monitor.get_metrics()


@router.get("/processes")
async def processes(user: dict = Depends(get_current_user)) -> dict[str, Any]:
    procs = await system.monitor.get_top_processes(20)
    return {"processes": procs}


# ── Apps ──────────────────────────────────────────────────────────────────────

@router.post("/apps/open")
async def open_app(req: AppRequest, user: dict = Depends(get_current_user)) -> dict:
    result = await system.apps.open_app(req.name)
    return {"success": result.success, "output": result.output, "error": result.error}


@router.post("/apps/close")
async def close_app(req: AppRequest, user: dict = Depends(get_current_user)) -> dict:
    result = await system.apps.close_app(req.name)
    return {"success": result.success}


@router.get("/apps/running")
async def running_apps(user: dict = Depends(get_current_user)) -> dict:
    procs = await system.apps.list_running()
    return {"processes": procs}


# ── Power ─────────────────────────────────────────────────────────────────────

@router.post("/power/lock")
async def lock(user: dict = Depends(get_current_user)) -> dict:
    result = await system.power.lock_screen()
    return {"success": result.success}


@router.post("/power/suspend")
async def suspend(user: dict = Depends(get_current_user)) -> dict:
    result = await system.power.suspend()
    return {"success": result.success}


@router.post("/power/shutdown")
async def shutdown(confirm: bool = False, user: dict = Depends(get_current_user)) -> dict:
    if not confirm:
        raise HTTPException(status_code=400, detail="Pass confirm=true to shutdown")
    result = await system.power.shutdown()
    return {"success": result.success}


@router.post("/power/restart")
async def restart(confirm: bool = False, user: dict = Depends(get_current_user)) -> dict:
    if not confirm:
        raise HTTPException(status_code=400, detail="Pass confirm=true to restart")
    result = await system.power.restart()
    return {"success": result.success}


# ── Audio ─────────────────────────────────────────────────────────────────────

@router.get("/audio/volume")
async def get_volume(user: dict = Depends(get_current_user)) -> dict:
    vol = await system.audio.get_volume()
    return {"volume": vol}


@router.post("/audio/volume")
async def set_volume(req: VolumeRequest, user: dict = Depends(get_current_user)) -> dict:
    result = await system.audio.set_volume(req.level)
    return {"success": result.success}


@router.post("/audio/mute")
async def mute(user: dict = Depends(get_current_user)) -> dict:
    result = await system.audio.mute()
    return {"success": result.success}


@router.post("/audio/unmute")
async def unmute(user: dict = Depends(get_current_user)) -> dict:
    result = await system.audio.unmute()
    return {"success": result.success}


# ── Brightness ────────────────────────────────────────────────────────────────

@router.post("/display/brightness")
async def set_brightness(req: BrightnessRequest, user: dict = Depends(get_current_user)) -> dict:
    result = await system.brightness.set_brightness(req.level)
    return {"success": result.success}


# ── Files ─────────────────────────────────────────────────────────────────────

@router.get("/files")
async def list_files(path: str = "~", user: dict = Depends(get_current_user)) -> dict:
    result = await system.files.list_dir(path)
    return {"success": result.success, "data": result.data, "error": result.error}


@router.post("/files/create")
async def create_file(req: FileRequest, user: dict = Depends(get_current_user)) -> dict:
    result = await system.files.create_file(req.path, req.content)
    return {"success": result.success, "output": result.output}


@router.delete("/files")
async def delete_file(req: FileRequest, user: dict = Depends(get_current_user)) -> dict:
    result = await system.files.delete(req.path, req.recursive)
    return {"success": result.success}


@router.post("/files/move")
async def move_file(req: MoveRequest, user: dict = Depends(get_current_user)) -> dict:
    result = await system.files.move(req.src, req.dst)
    return {"success": result.success}


# ── Screenshot ────────────────────────────────────────────────────────────────

@router.post("/screenshot")
async def screenshot(user: dict = Depends(get_current_user)) -> dict:
    result = await system.media.screenshot()
    return {"success": result.success, "path": result.data.get("path", ""), "error": result.error}


# ── Network ───────────────────────────────────────────────────────────────────

@router.get("/network")
async def network_status(user: dict = Depends(get_current_user)) -> dict:
    return await system.network.get_status()


@router.post("/network/wifi/on")
async def wifi_on(user: dict = Depends(get_current_user)) -> dict:
    result = await system.network.wifi_on()
    return {"success": result.success}


@router.post("/network/wifi/off")
async def wifi_off(user: dict = Depends(get_current_user)) -> dict:
    result = await system.network.wifi_off()
    return {"success": result.success}


# ── Clipboard ─────────────────────────────────────────────────────────────────

@router.get("/clipboard")
async def get_clipboard(user: dict = Depends(get_current_user)) -> dict:
    result = await system.clipboard.get()
    return {"content": result.output}


@router.post("/clipboard")
async def set_clipboard(req: ClipboardRequest, user: dict = Depends(get_current_user)) -> dict:
    result = await system.clipboard.set(req.text)
    return {"success": result.success}


# ── Shell ─────────────────────────────────────────────────────────────────────

@router.post("/shell")
async def run_shell(req: ShellRequest, user: dict = Depends(get_current_user)) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin required for shell access")
    result = await system.execute_shell(req.command)
    return {
        "success": result.success,
        "output": result.output,
        "error": result.error,
        "return_code": result.return_code,
    }


# ── Input ─────────────────────────────────────────────────────────────────────

@router.post("/input/type")
async def type_text(req: TypeRequest, user: dict = Depends(get_current_user)) -> dict:
    result = await system.input.type_text(req.text)
    return {"success": result.success}
