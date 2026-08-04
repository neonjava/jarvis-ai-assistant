"""
WebSocket Hub — Real-time bidirectional communication
Handles: voice events, system metrics, notifications, command responses
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

ws_router = APIRouter()


class ConnectionManager:
    """Manages all active WebSocket connections."""

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, ws: WebSocket, client_id: str) -> None:
        await ws.accept()
        self._connections[client_id] = ws
        logger.info(f"WebSocket connected: {client_id} | Total: {len(self._connections)}")
        await self.send_to(client_id, {"type": "connected", "message": "JARVIS WebSocket ready"})

    def disconnect(self, client_id: str) -> None:
        self._connections.pop(client_id, None)
        logger.info(f"WebSocket disconnected: {client_id}")

    async def send_to(self, client_id: str, data: dict[str, Any]) -> None:
        ws = self._connections.get(client_id)
        if ws:
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(client_id)

    async def broadcast(self, data: dict[str, Any]) -> None:
        dead = []
        for client_id, ws in self._connections.items():
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(client_id)
        for client_id in dead:
            self.disconnect(client_id)

    @property
    def connected_count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()


@ws_router.websocket("/ws/{client_id}")
async def websocket_endpoint(ws: WebSocket, client_id: str) -> None:
    from ai.engine import ai_engine
    from ai.interpreter import CommandInterpreter
    from system.controller import system

    interpreter = CommandInterpreter(ai_engine, system)

    await manager.connect(ws, client_id)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = {"type": "chat", "message": raw}

            msg_type = data.get("type", "chat")

            if msg_type == "ping":
                await manager.send_to(client_id, {"type": "pong"})

            elif msg_type in ("chat", "command"):
                message = data.get("message", "")
                stream = data.get("stream", False)

                if stream:
                    # Send streaming response
                    await manager.send_to(client_id, {"type": "stream_start"})
                    full = ""
                    async for chunk in ai_engine.stream_chat(message):
                        full += chunk
                        await manager.send_to(client_id, {"type": "stream_chunk", "chunk": chunk})
                    await manager.send_to(client_id, {
                        "type": "stream_end",
                        "message": full,
                    })
                else:
                    cmd = await interpreter.parse(message)
                    if cmd.requires_confirmation:
                        await manager.send_to(client_id, {
                            "type": "confirmation_required",
                            "action": cmd.action,
                            "message": cmd.danger_message,
                            "cmd_raw": message,
                        })
                    else:
                        response, result = await interpreter.execute(cmd)
                        await manager.send_to(client_id, {
                            "type": "response",
                            "message": response,
                            "success": result.success if result else True,
                            "data": result.data if result else {},
                        })

            elif msg_type == "confirm_execute":
                message = data.get("cmd_raw", "")
                cmd = await interpreter.parse(message)
                cmd.requires_confirmation = False  # User confirmed
                response, result = await interpreter.execute(cmd)
                await manager.send_to(client_id, {
                    "type": "response",
                    "message": response,
                    "success": result.success if result else True,
                })

            elif msg_type == "metrics":
                metrics = await system.monitor.get_metrics()
                await manager.send_to(client_id, {"type": "metrics", "data": metrics})

            elif msg_type == "clear_memory":
                ai_engine.clear_memory()
                await manager.send_to(client_id, {"type": "memory_cleared"})

    except WebSocketDisconnect:
        manager.disconnect(client_id)


async def broadcast_notification(title: str, body: str, source: str = "system") -> None:
    """Broadcast a notification to all connected clients."""
    await manager.broadcast({
        "type": "notification",
        "title": title,
        "body": body,
        "source": source,
    })


async def broadcast_metrics(metrics: dict[str, Any]) -> None:
    """Broadcast system metrics to all clients."""
    await manager.broadcast({"type": "metrics", "data": metrics})
