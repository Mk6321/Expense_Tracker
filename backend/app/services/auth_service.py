from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AuthError, ConflictError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import User
from app.repositories import user_repo


async def register(db: AsyncSession, *, name: str, email: str, password: str) -> User:
    if await user_repo.get_by_email(db, email) is not None:
        raise ConflictError("An account with this email already exists.", "EMAIL_TAKEN")
    user = await user_repo.create(
        db, name=name, email=email, password_hash=hash_password(password)
    )
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate(db: AsyncSession, *, email: str, password: str) -> User:
    user = await user_repo.get_by_email(db, email)
    # Hash the supplied password even when the user is missing, so a wrong email and
    # a wrong password take the same time and cannot be told apart by timing.
    password_hash = user.password_hash if user else hash_password("timing-equaliser")
    valid = verify_password(password, password_hash)

    if user is None or not valid:
        raise AuthError("Incorrect email or password.", "INVALID_CREDENTIALS")
    if not user.is_active:
        raise AuthError("This account has been deactivated.", "USER_INACTIVE")
    return user


async def refresh_session(db: AsyncSession, refresh_token: str | None) -> tuple[User, str, str]:
    """Validate a refresh token and rotate it -- the old jti is never reissued."""
    if not refresh_token:
        raise AuthError("No refresh token supplied.", "REFRESH_MISSING")

    payload = decode_token(refresh_token, "refresh")
    user = await user_repo.get_by_id(db, int(payload["sub"]))
    if user is None or not user.is_active:
        raise AuthError("User is no longer active.", "USER_INACTIVE")

    return user, create_access_token(user.id), create_refresh_token(user.id)


def issue_tokens(user: User) -> tuple[str, str, int]:
    return (
        create_access_token(user.id),
        create_refresh_token(user.id),
        settings.JWT_ACCESS_TOKEN_EXPIRE,
    )
