"""
Security Module — JWT Auth, Password Hashing, Permission System
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from loguru import logger
from passlib.context import CryptContext

from config.settings import settings

# ── Password Hashing ──────────────────────────────────────────────────────────

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ── JWT Tokens ────────────────────────────────────────────────────────────────

def create_access_token(data: dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: str) -> tuple[str, str]:
    """Return (raw_token, hashed_token)."""
    raw = secrets.token_urlsafe(64)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


def decode_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


# ── FastAPI Auth Dependencies ─────────────────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> dict[str, Any]:
    """FastAPI dependency: validate JWT and return payload."""
    if not settings.REQUIRE_AUTH:
        return {"sub": "local", "is_admin": True}

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(credentials.credentials)
    return payload


async def require_admin(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    if not user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


# ── Permission System ─────────────────────────────────────────────────────────

class Permission:
    """Granular permission flags."""

    SYSTEM_READ = "system:read"
    SYSTEM_WRITE = "system:write"
    SYSTEM_DANGEROUS = "system:dangerous"
    FILES_READ = "files:read"
    FILES_WRITE = "files:write"
    AI_CHAT = "ai:chat"
    PLUGINS_MANAGE = "plugins:manage"
    ADMIN = "admin"

    ALL = [SYSTEM_READ, SYSTEM_WRITE, FILES_READ, FILES_WRITE, AI_CHAT]
    ADMIN_ONLY = [SYSTEM_DANGEROUS, PLUGINS_MANAGE, ADMIN]


DANGEROUS_COMMANDS = {
    "shutdown", "restart", "hibernate", "kill_app",
    "delete_file", "format_disk", "run_command",
}


def is_dangerous(action: str) -> bool:
    return action in DANGEROUS_COMMANDS


# ── IP Whitelist ──────────────────────────────────────────────────────────────

def is_allowed_ip(client_ip: str) -> bool:
    if not settings.ALLOWED_IPS:
        return True  # All IPs allowed
    return client_ip in settings.ALLOWED_IPS


# ── API Key Generation ────────────────────────────────────────────────────────

def generate_api_key() -> str:
    return f"jv_{secrets.token_urlsafe(32)}"
