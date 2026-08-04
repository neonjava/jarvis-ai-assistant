"""Auth routes — login, refresh, register."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.engine import get_db
from database.models import User, RefreshToken
from security.auth import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    get_current_user,
)
from config.settings import settings

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    is_admin: bool


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    access_token = create_access_token({"sub": user.id, "is_admin": user.is_admin})
    raw_refresh, hashed_refresh = create_refresh_token(user.id)

    token = RefreshToken(
        user_id=user.id,
        token_hash=hashed_refresh,
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(token)
    user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        user_id=user.id,
        username=user.username,
        is_admin=user.is_admin,
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    existing = await db.execute(select(User).where(User.username == req.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already taken")

    # First user is always admin
    count_result = await db.execute(select(User))
    is_first_user = count_result.first() is None

    user = User(
        username=req.username,
        hashed_password=hash_password(req.password),
        email=req.email,
        is_admin=is_first_user,
    )
    db.add(user)
    await db.flush()

    access_token = create_access_token({"sub": user.id, "is_admin": user.is_admin})
    raw_refresh, hashed_refresh = create_refresh_token(user.id)
    token = RefreshToken(
        user_id=user.id,
        token_hash=hashed_refresh,
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        user_id=user.id,
        username=user.username,
        is_admin=user.is_admin,
    )


@router.get("/me")
async def me(user: dict = Depends(get_current_user)) -> dict:
    return user
