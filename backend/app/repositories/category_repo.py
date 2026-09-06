from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category

# Seeded once as global rows (group_id NULL) so every group starts with something.
DEFAULT_CATEGORIES: list[tuple[str, str]] = [
    ("Food & Drink", "utensils"),
    ("Groceries", "shopping-cart"),
    ("Rent", "home"),
    ("Utilities", "plug"),
    ("Transport", "car"),
    ("Entertainment", "film"),
    ("Travel", "plane"),
    ("Shopping", "shopping-bag"),
    ("Health", "heart-pulse"),
    ("Other", "circle-dashed"),
]


async def list_for_group(db: AsyncSession, group_id: int) -> list[Category]:
    """Global defaults plus this group's own categories."""
    result = await db.execute(
        select(Category)
        .where(
            or_(Category.group_id.is_(None), Category.group_id == group_id),
            Category.is_active.is_(True),
        )
        .order_by(Category.group_id.is_(None).desc(), Category.name)
    )
    return list(result.scalars())


async def get(db: AsyncSession, category_id: int) -> Category | None:
    return await db.get(Category, category_id)


async def create(
    db: AsyncSession, *, group_id: int | None, name: str, icon: str | None
) -> Category:
    category = Category(group_id=group_id, name=name, icon=icon, is_active=True)
    db.add(category)
    await db.flush()
    return category


async def ensure_defaults(db: AsyncSession) -> int:
    """Idempotent seed of the global default categories."""
    result = await db.execute(select(Category.name).where(Category.group_id.is_(None)))
    existing = set(result.scalars())
    created = 0
    for name, icon in DEFAULT_CATEGORIES:
        if name not in existing:
            db.add(Category(group_id=None, name=name, icon=icon, is_active=True))
            created += 1
    if created:
        await db.flush()
    return created
