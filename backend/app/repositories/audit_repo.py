from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, IdempotencyKey


async def record(
    db: AsyncSession,
    *,
    group_id: int | None,
    user_id: int,
    entity_type: str,
    entity_id: int,
    action: str,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
) -> AuditLog:
    """Written inside the caller's transaction, so the log and the change it
    describes commit together or not at all (Section 4)."""
    entry = AuditLog(
        group_id=group_id,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        old_value=old_value,
        new_value=new_value,
    )
    db.add(entry)
    return entry


async def list_for_group(db: AsyncSession, group_id: int, limit: int = 50) -> list[AuditLog]:
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.group_id == group_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
    )
    return list(result.scalars())


async def get_idempotent_response(
    db: AsyncSession, *, key: str, user_id: int, endpoint: str
) -> dict[str, Any] | None:
    result = await db.execute(
        select(IdempotencyKey).where(
            IdempotencyKey.key == key,
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.endpoint == endpoint,
        )
    )
    row = result.scalar_one_or_none()
    return row.response_body if row else None


async def store_idempotent_response(
    db: AsyncSession, *, key: str, user_id: int, endpoint: str, response_body: dict[str, Any]
) -> None:
    db.add(
        IdempotencyKey(
            key=key, user_id=user_id, endpoint=endpoint, response_body=response_body
        )
    )
