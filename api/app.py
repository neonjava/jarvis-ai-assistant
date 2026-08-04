"""
FastAPI Application — REST + WebSocket API
"""
from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel

from config.settings import settings
from database.engine import close_db, init_db
from security.auth import get_current_user


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown logic."""
    logger.info(f"🚀 Starting JARVIS API v{settings.APP_VERSION}")

    # Database
    await init_db()

    # AI Engine
    from ai.engine import ai_engine
    await ai_engine.initialize()

    # Voice (if enabled)
    if settings.VOICE_ENABLED:
        from voice.pipeline import voice_pipeline
        from ai.interpreter import CommandInterpreter
        from system.controller import system

        interpreter = CommandInterpreter(ai_engine, system)

        async def voice_command_handler(text: str) -> None:
            response, _ = await interpreter.execute(await interpreter.parse(text))
            await voice_pipeline.speak(response)

        voice_pipeline.on_command(voice_command_handler)
        asyncio.create_task(voice_pipeline.initialize())

    logger.info("✅ JARVIS API ready")
    yield

    # Shutdown
    logger.info("Shutting down JARVIS...")
    if settings.VOICE_ENABLED:
        from voice.pipeline import voice_pipeline
        await voice_pipeline.stop()
    await close_db()


# ── App Factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="JARVIS API",
        description="AI Desktop Assistant — REST + WebSocket API",
        version=settings.APP_VERSION,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Register routes
    from api.routes import auth, chat, system as sys_routes, notifications, plugins, metrics

    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
    app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
    app.include_router(sys_routes.router, prefix="/api/v1/system", tags=["System"])
    app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["Notifications"])
    app.include_router(plugins.router, prefix="/api/v1/plugins", tags=["Plugins"])
    app.include_router(metrics.router, prefix="/api/v1/metrics", tags=["Metrics"])

    # WebSocket
    from api.websocket import ws_router
    app.include_router(ws_router)

    # Health check
    @app.get("/health", tags=["Health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": settings.APP_VERSION}

    return app


app = create_app()
