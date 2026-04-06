"""
JWT authentication with backward-compatible static Bearer fallback.

Auth modes (determined at request time):
1. API_SECRET_KEY unset → anonymous admin (local dev)
2. API_SECRET_KEY set + USERS_FILE exists → JWT authentication
3. API_SECRET_KEY set + no USERS_FILE → static Bearer token fallback
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt as jose_jwt
from pydantic import BaseModel

from .users import User, UserRole, UserStore

_bearer = HTTPBearer(auto_error=False)

# Token lifetime: 24 hours
TOKEN_EXPIRE_SECONDS = 86400


class TokenRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = TOKEN_EXPIRE_SECONDS


class UserContext(BaseModel):
    user_id: str
    role: UserRole
    email: str


def _get_secret() -> str | None:
    return os.getenv("API_SECRET_KEY")


def _get_user_store() -> UserStore | None:
    """Return a UserStore if USERS_FILE is configured, else None."""
    path = os.getenv("USERS_FILE")
    if not path:
        return None
    return UserStore(path)


def create_token(user: User) -> TokenResponse:
    """Issue a JWT for an authenticated user."""
    secret = _get_secret()
    if not secret:
        raise HTTPException(500, "API_SECRET_KEY not configured")
    exp = datetime.now(timezone.utc) + timedelta(seconds=TOKEN_EXPIRE_SECONDS)
    payload = {
        "sub": user.user_id,
        "role": user.role.value,
        "exp": exp,
    }
    token = jose_jwt.encode(payload, secret, algorithm="HS256")
    return TokenResponse(access_token=token, expires_in=TOKEN_EXPIRE_SECONDS)


def authenticate_user(email: str, password: str) -> User:
    """Validate credentials and return the User, or raise 401."""
    user_store = _get_user_store()
    if user_store is None:
        raise HTTPException(401, "用户系统未配置")
    user = user_store.get_by_email(email)
    if user is None:
        raise HTTPException(401, "邮箱或密码错误")
    if not user.is_active:
        raise HTTPException(401, "用户已禁用")
    if not bcrypt.checkpw(password.encode("utf-8"), user.hashed_pwd.encode("utf-8")):
        raise HTTPException(401, "邮箱或密码错误")
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> UserContext:
    """Resolve the current user from the Authorization header.

    Three modes:
    1. No API_SECRET_KEY → anonymous admin (local dev)
    2. API_SECRET_KEY + USERS_FILE → JWT decode
    3. API_SECRET_KEY + no USERS_FILE → static Bearer
    """
    secret = _get_secret()

    # Mode 1: no secret → anonymous admin
    if not secret:
        return UserContext(user_id="anonymous", role=UserRole.admin, email="anonymous@local")

    # Secret is configured → require credentials
    if not credentials:
        raise HTTPException(status_code=401, detail="未提供认证凭据")

    token = credentials.credentials

    # Mode 3: static Bearer fallback (no users file)
    users_file = os.getenv("USERS_FILE")
    if not users_file:
        if token == secret:
            return UserContext(user_id="static-bearer", role=UserRole.admin, email="bearer@static")
        raise HTTPException(status_code=401, detail="Invalid or missing token")

    # Mode 2: JWT decode
    try:
        payload = jose_jwt.decode(token, secret, algorithms=["HS256"])
        return UserContext(
            user_id=payload["sub"],
            role=UserRole(payload["role"]),
            email=payload.get("email", ""),
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
