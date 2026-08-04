"""
JARVIS Configuration System
Loads all settings from environment variables / .env file.
"""
from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Core application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── App ──────────────────────────────────────────────────────────────
    APP_NAME: str = "JARVIS"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Path = Path("logs/jarvis.log")
    DATA_DIR: Path = Path("data")

    # ── API Server ────────────────────────────────────────────────────────
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8765
    API_WORKERS: int = 1
    API_RELOAD: bool = True
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8080"]

    # ── Security ──────────────────────────────────────────────────────────
    SECRET_KEY: str = secrets.token_hex(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    REQUIRE_AUTH: bool = True
    ALLOWED_IPS: list[str] = []

    # ── Database ──────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/jarvis.db"

    # ── AI / LLM ──────────────────────────────────────────────────────────
    AI_PROVIDER: str = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"
    OLLAMA_TIMEOUT: int = 60
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    AI_MAX_TOKENS: int = 2048
    AI_TEMPERATURE: float = 0.7
    AI_SYSTEM_PROMPT: str = (
        "You are JARVIS, an advanced AI assistant for a Fedora Linux desktop. "
        "You are precise, concise, and professional. When asked to perform system actions, "
        "always confirm dangerous operations. Respond naturally and helpfully."
    )
    MEMORY_MAX_TURNS: int = 20

    # ── Voice ─────────────────────────────────────────────────────────────
    VOICE_ENABLED: bool = True
    WAKE_WORD: str = "jarvis"
    WAKE_WORD_THRESHOLD: float = 0.7
    STT_PROVIDER: str = "faster-whisper"
    STT_MODEL: str = "base.en"
    STT_DEVICE: str = "cpu"
    TTS_PROVIDER: str = "piper"
    PIPER_MODEL: str = "en_US-lessac-medium"
    AUDIO_SAMPLE_RATE: int = 16000
    AUDIO_CHANNELS: int = 1
    MIC_INDEX: Optional[int] = None

    @field_validator("MIC_INDEX", mode="before")
    @classmethod
    def coerce_mic_index(cls, v: Any) -> Optional[int]:
        if v is None or v == "" or str(v).strip() == "":
            return None
        return int(v)

    # ── Notifications ─────────────────────────────────────────────────────
    NOTIFICATIONS_ENABLED: bool = True
    DISCORD_TOKEN: Optional[str] = None
    DISCORD_GUILD_ID: Optional[str] = None
    GITHUB_TOKEN: Optional[str] = None
    GITHUB_REPOS: list[str] = []
    GMAIL_CREDENTIALS_FILE: Optional[Path] = None
    BATTERY_WARNING_THRESHOLD: int = 20

    # ── Monitoring ────────────────────────────────────────────────────────
    MONITOR_INTERVAL: int = 5
    CPU_ALERT_THRESHOLD: float = 90.0
    RAM_ALERT_THRESHOLD: float = 90.0
    DISK_ALERT_THRESHOLD: float = 90.0
    TEMP_ALERT_THRESHOLD: float = 80.0

    # ── Weather ───────────────────────────────────────────────────────────
    WEATHER_API_KEY: Optional[str] = None
    WEATHER_CITY: Optional[str] = None

    # ── Plugins ───────────────────────────────────────────────────────────
    PLUGINS_ENABLED: bool = True
    PLUGINS_DIR: Path = Path("plugins/installed")
    PLUGIN_SANDBOX: bool = True

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid:
            raise ValueError(f"LOG_LEVEL must be one of {valid}")
        return v.upper()

    @field_validator("APP_ENV")
    @classmethod
    def validate_env(cls, v: str) -> str:
        valid = {"development", "production", "testing"}
        if v.lower() not in valid:
            raise ValueError(f"APP_ENV must be one of {valid}")
        return v.lower()

    @model_validator(mode="after")
    def ensure_directories(self) -> "AppSettings":
        """Create required directories on startup."""
        for d in [self.DATA_DIR, self.LOG_FILE.parent, self.PLUGINS_DIR]:
            Path(d).mkdir(parents=True, exist_ok=True)
        return self

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return cached singleton settings instance."""
    return AppSettings()


# Convenience alias
settings = get_settings()
