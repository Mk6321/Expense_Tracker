from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import audit_repo


async def replay(
    db: AsyncSession, *, key: str | None, user_id: int, endpoint: str
) -> dict[str, Any] | None:
    """Returns the stored response for a key we have already handled (Section 7)."""
    if not key:
        return None
    return await audit_repo.get_idempotent_response(
        db, key=key, user_id=user_id, endpoint=endpoint
    )


async def remember(
    db: AsyncSession,
    *,
    key: str | None,
    user_id: int,
    endpoint: str,
    response_body: dict[str, Any],
) -> None:
    """Stored after the write commits, in its own transaction.

    A retry that arrives in the window between the two commits can still duplicate,
    which is why the key is also the primary key: the second insert loses on the
    unique constraint rather than corrupting anything.
    """
    if not key:
        return
    try:
        await audit_repo.store_idempotent_response(
            db, key=key, user_id=user_id, endpoint=endpoint, response_body=response_body
        )
        await db.commit()
    except Exception:
        await db.rollback()
