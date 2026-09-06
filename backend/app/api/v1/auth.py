from __future__ import annotations

from fastapi import APIRouter, Cookie, Response, status

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession
from app.schemas.auth import LoginRequest, RegisterRequest, TokenOut, UserOut
from app.schemas.common import Envelope
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_refresh_cookie(response: Response, token: str) -> None:
    """httpOnly + Secure + SameSite=None so it survives the Vercel/Render origin
    split without ever being readable from JS (Section 11)."""
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE,
        path="/api/v1/auth",
    )


@router.post("/register", response_model=Envelope[TokenOut], status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, response: Response, db: DbSession):
    user = await auth_service.register(
        db, name=payload.name, email=payload.email, password=payload.password
    )
    access, refresh, expires_in = auth_service.issue_tokens(user)
    _set_refresh_cookie(response, refresh)
    return Envelope(
        data=TokenOut(
            access_token=access, expires_in=expires_in, user=UserOut.model_validate(user)
        ),
        message="Account created.",
    )


@router.post("/login", response_model=Envelope[TokenOut])
async def login(payload: LoginRequest, response: Response, db: DbSession):
    user = await auth_service.authenticate(db, email=payload.email, password=payload.password)
    access, refresh, expires_in = auth_service.issue_tokens(user)
    _set_refresh_cookie(response, refresh)
    return Envelope(
        data=TokenOut(
            access_token=access, expires_in=expires_in, user=UserOut.model_validate(user)
        )
    )


@router.post("/refresh", response_model=Envelope[TokenOut])
async def refresh(response: Response, db: DbSession, et_refresh: str | None = Cookie(None)):
    user, access, new_refresh = await auth_service.refresh_session(db, et_refresh)
    # Rotation: every refresh mints a new token and replaces the cookie.
    _set_refresh_cookie(response, new_refresh)
    return Envelope(
        data=TokenOut(
            access_token=access,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE,
            user=UserOut.model_validate(user),
        )
    )


@router.post("/logout", response_model=Envelope[dict])
async def logout(response: Response):
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path="/api/v1/auth",
        domain=settings.COOKIE_DOMAIN,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )
    return Envelope(data={}, message="Signed out.")


@router.get("/me", response_model=Envelope[UserOut])
async def me(user: CurrentUser):
    return Envelope(data=UserOut.model_validate(user))
