from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


async def get_by_id(db: AsyncSession, user_id: int) -> User | None:
    return await db.get(User, user_id)


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def get_many(db: AsyncSession, user_ids: list[int]) -> list[User]:
    if not user_ids:
        return []
    result = await db.execute(select(User).where(User.id.in_(user_ids)))
    return list(result.scalars())


async def create(db: AsyncSession, *, name: str, email: str, password_hash: str) -> User:
    user = User(name=name, email=email.lower(), password_hash=password_hash, is_active=True)
    db.add(user)
    await db.flush()
    return user
