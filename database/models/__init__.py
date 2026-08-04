"""
Database Models — SQLAlchemy 2.0 async ORM
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base model with common fields."""

    __abstract__ = True

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


# ─────────────────────────────────────────────────────────────
# User & Auth
# ─────────────────────────────────────────────────────────────

class User(Base):
    """System users (local + mobile app users)."""

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user")
    sessions: Mapped[list["Conversation"]] = relationship(back_populates="user")


class RefreshToken(Base):
    """Refresh tokens for persistent login."""

    __tablename__ = "refresh_tokens"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    device_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship(back_populates="tokens")


# ─────────────────────────────────────────────────────────────
# Conversations & Memory
# ─────────────────────────────────────────────────────────────

class Conversation(Base):
    """A chat session with JARVIS."""

    __tablename__ = "conversations"

    user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_voice: Mapped[bool] = mapped_column(Boolean, default=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped[Optional["User"]] = relationship(back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")


class Message(Base):
    """Individual message in a conversation."""

    __tablename__ = "messages"

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(32))  # user | assistant | system
    content: Mapped[str] = mapped_column(Text)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    audio_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    __table_args__ = (Index("ix_messages_conv_created", "conversation_id", "created_at"),)


class MemoryFact(Base):
    """Long-term memory facts about the user / system."""

    __tablename__ = "memory_facts"

    key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(64), default="general")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)


# ─────────────────────────────────────────────────────────────
# Commands & Audit
# ─────────────────────────────────────────────────────────────

class CommandLog(Base):
    """Audit log for every command executed."""

    __tablename__ = "command_logs"

    user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    command_type: Mapped[str] = mapped_column(String(64), index=True)
    command_name: Mapped[str] = mapped_column(String(128))
    parameters: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    status: Mapped[str] = mapped_column(String(32), default="pending")
    output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="text")  # voice|text|api|mobile


class Notification(Base):
    """Stored notifications."""

    __tablename__ = "notifications"

    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(64))  # system|discord|github|gmail
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    action_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class PluginRecord(Base):
    """Installed plugins registry."""

    __tablename__ = "plugins"

    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    version: Mapped[str] = mapped_column(String(32))
    author: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON


class SystemMetric(Base):
    """Periodic system metrics snapshots."""

    __tablename__ = "system_metrics"

    cpu_percent: Mapped[float] = mapped_column(Float)
    ram_percent: Mapped[float] = mapped_column(Float)
    ram_used_gb: Mapped[float] = mapped_column(Float)
    disk_percent: Mapped[float] = mapped_column(Float)
    cpu_temp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    network_up_mbps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    network_down_mbps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    __table_args__ = (Index("ix_metrics_created", "created_at"),)


class ScheduledTask(Base):
    """User-defined scheduled automations."""

    __tablename__ = "scheduled_tasks"

    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cron_expression: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    interval_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    command: Mapped[str] = mapped_column(Text)  # JSON command payload
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0)
