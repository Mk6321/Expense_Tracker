from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.errors import AuthError, GroupAccessDenied, PermissionDenied
from app.core.security import decode_token
from app.models import Group, GroupMember, User
from app.models.enums import MemberRole
from app.repositories import group_repo, user_repo

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("Missing bearer token.", "TOKEN_MISSING")

    payload = decode_token(authorization.split(" ", 1)[1].strip(), "access")
    user = await user_repo.get_by_id(db, int(payload["sub"]))
    if user is None or not user.is_active:
        raise AuthError("User is no longer active.", "USER_INACTIVE")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@dataclass
class GroupContext:
    """Everything a group-scoped route needs, already authorised."""

    group: Group
    membership: GroupMember
    user: User

    @property
    def group_id(self) -> int:
        return self.group.id

    @property
    def role(self) -> str:
        return self.membership.role

    @property
    def is_admin(self) -> bool:
        return self.membership.role == MemberRole.ADMIN.value

    @property
    def can_write(self) -> bool:
        return self.membership.role in (MemberRole.ADMIN.value, MemberRole.MEMBER.value)

    def require_admin(self) -> None:
        if not self.is_admin:
            raise PermissionDenied("Only a group admin can do this.", "ADMIN_REQUIRED")

    def require_write(self) -> None:
        if not self.can_write:
            raise PermissionDenied(
                "Viewers have read-only access to this group.", "READ_ONLY_ROLE"
            )

    def require_active_group(self) -> None:
        if self.group.is_archived:
            raise PermissionDenied("This group is archived.", "GROUP_ARCHIVED")


async def get_current_group_membership(
    db: DbSession,
    user: CurrentUser,
    group_id: Annotated[int, Path()],
) -> GroupContext:
    """The single membership gate for every group-scoped route (Section 5).

    Deliberately 404s rather than 403s: a 403 would confirm that a group id exists
    to someone who is just guessing ids.
    """
    group = await group_repo.get(db, group_id)
    if group is None:
        raise GroupAccessDenied()

    membership = await group_repo.get_membership(
        db, group_id=group_id, user_id=user.id, active_only=True
    )
    if membership is None:
        raise GroupAccessDenied()

    return GroupContext(group=group, membership=membership, user=user)


GroupCtx = Annotated[GroupContext, Depends(get_current_group_membership)]


def get_idempotency_key(
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str | None:
    return idempotency_key.strip() if idempotency_key else None


IdempotencyKeyHeader = Annotated[str | None, Depends(get_idempotency_key)]
