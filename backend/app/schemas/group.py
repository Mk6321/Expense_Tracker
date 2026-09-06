from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import MemberRole
from app.schemas.common import AppModel, Money


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    currency: str = Field(default="INR", min_length=3, max_length=3)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Group name cannot be blank.")
        return v

    @field_validator("currency")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class GroupOut(AppModel):
    id: int
    name: str
    currency: str
    created_by: int
    is_archived: bool
    created_at: datetime
    # Denormalised for the group list -- filled in by the service, not the ORM.
    role: str | None = None
    member_count: int | None = None
    my_balance: Money | None = None


class MemberOut(BaseModel):
    user_id: int
    name: str
    email: str
    role: str
    status: str
    joined_at: datetime


class RoleUpdate(BaseModel):
    role: MemberRole


class InviteOut(BaseModel):
    code: str
    group_id: int
    expires_at: datetime
    is_revoked: bool


class JoinRequest(BaseModel):
    invite_code: str = Field(min_length=4, max_length=16)

    @field_validator("invite_code")
    @classmethod
    def _normalise(cls, v: str) -> str:
        return v.strip().upper()


class RemoveMemberResult(BaseModel):
    user_id: int
    status: str
    forced: bool = False
    outstanding_balance: Money | None = None
