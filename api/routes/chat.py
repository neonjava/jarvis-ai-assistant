"""Chat routes — text-based AI interaction."""
from __future__ import annotations

from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ai.engine import ai_engine
from ai.interpreter import CommandInterpreter
from system.controller import system
from security.auth import get_current_user

router = APIRouter()

_interpreter = CommandInterpreter(ai_engine, system)


class ChatRequest(BaseModel):
    message: str
    stream: bool = False
    context: str = ""


class CommandRequest(BaseModel):
    command: str
    confirm: bool = False


@router.post("/message")
async def chat_message(
    req: ChatRequest,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Send a chat message and get a response."""
    response = await ai_engine.chat(req.message, context=req.context)
    return {"response": response, "success": True}


@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    user: dict = Depends(get_current_user),
) -> StreamingResponse:
    """Stream a chat response using SSE."""
    async def generate() -> AsyncGenerator[str, None]:
        async for chunk in ai_engine.stream_chat(req.message):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/command")
async def execute_command(
    req: CommandRequest,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Parse and execute a natural language command."""
    cmd = await _interpreter.parse(req.command)

    if cmd.requires_confirmation and not req.confirm:
        return {
            "requires_confirmation": True,
            "action": cmd.action,
            "message": cmd.danger_message,
        }

    response, result = await _interpreter.execute(cmd)
    return {
        "response": response,
        "success": result.success if result else True,
        "data": result.data if result else {},
        "action": cmd.action,
    }


@router.delete("/memory")
async def clear_memory(user: dict = Depends(get_current_user)) -> dict:
    ai_engine.clear_memory()
    return {"message": "Conversation memory cleared"}


@router.get("/models")
async def list_models(user: dict = Depends(get_current_user)) -> dict:
    models = await ai_engine.get_available_models()
    return {"models": models}
