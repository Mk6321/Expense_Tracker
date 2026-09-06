from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.errors import AuthError

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

TokenType = Literal["access", "refresh"]


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


def _create_token(subject: str, token_type: TokenType, expires_in: int, **extra: Any) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
        "jti": secrets.token_urlsafe(16),
        **extra,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: int) -> str:
    return _create_token(str(user_id), "access", settings.JWT_ACCESS_TOKEN_EXPIRE)


def create_refresh_token(user_id: int) -> str:
    """A fresh jti on every issue -- rotation on use is handled by the auth service."""
    return _create_token(str(user_id), "refresh", settings.JWT_REFRESH_TOKEN_EXPIRE)


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise AuthError("Token has expired.", "TOKEN_EXPIRED")
    except jwt.PyJWTError:
        raise AuthError("Invalid token.", "TOKEN_INVALID")

    if payload.get("type") != expected_type:
        raise AuthError("Invalid token type.", "TOKEN_INVALID")
    if not payload.get("sub"):
        raise AuthError("Invalid token.", "TOKEN_INVALID")
    return payload


def generate_invite_code() -> str:
    """Short, URL-safe, unambiguous invite code."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(8))
