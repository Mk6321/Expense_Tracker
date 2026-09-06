from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import AppModel


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be blank.")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(AppModel):
    id: int
    name: str
    email: str
    is_active: bool
    created_at: datetime


class TokenOut(BaseModel):
    """The refresh token is set as an httpOnly cookie, never returned in the body."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
