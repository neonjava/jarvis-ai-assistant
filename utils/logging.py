"""
JARVIS Logging Configuration
Rich-formatted, async-friendly logging powered by Loguru.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from loguru import logger
from rich.console import Console
from rich.logging import RichHandler

from config.settings import settings

console = Console(highlight=True)


def setup_logging() -> None:
    """Configure loguru with rich console + file sink."""
    logger.remove()  # Remove default handler

    # ── Console handler (Rich) ──────────────────────────────────────────
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    logger.add(
        sys.stdout,
        format=log_format,
        level=settings.LOG_LEVEL,
        colorize=True,
        backtrace=True,
        diagnose=settings.DEBUG,
    )

    # ── File handler ────────────────────────────────────────────────────
    log_file = settings.LOG_FILE
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        str(log_file),
        format=log_format,
        level=settings.LOG_LEVEL,
        rotation="10 MB",
        retention="7 days",
        compression="gz",
        backtrace=True,
        diagnose=settings.DEBUG,
        enqueue=True,  # async-safe
    )

    logger.info(
        f"🤖 JARVIS v{settings.APP_VERSION} logging initialized "
        f"[{settings.APP_ENV.upper()}] [{settings.LOG_LEVEL}]"
    )


def get_logger(name: str) -> Any:
    """Get a named logger instance."""
    return logger.bind(name=name)
