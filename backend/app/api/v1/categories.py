from __future__ import annotations

from fastapi import APIRouter, status

from app.core.deps import DbSession, GroupCtx
from app.repositories import audit_repo, category_repo
from app.models.enums import AuditAction
from app.schemas.common import Envelope
from app.schemas.report import CategoryCreate, CategoryOut

router = APIRouter(tags=["categories"])


@router.get("/groups/{group_id}/categories", response_model=Envelope[list[CategoryOut]])
async def list_categories(ctx: GroupCtx, db: DbSession):
    rows = await category_repo.list_for_group(db, ctx.group_id)
    return Envelope(data=[CategoryOut.model_validate(c) for c in rows])


@router.post(
    "/groups/{group_id}/categories",
    response_model=Envelope[CategoryOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_category(payload: CategoryCreate, ctx: GroupCtx, db: DbSession):
    ctx.require_admin()
    category = await category_repo.create(
        db, group_id=ctx.group_id, name=payload.name.strip(), icon=payload.icon
    )
    await audit_repo.record(
        db,
        group_id=ctx.group_id,
        user_id=ctx.user.id,
        entity_type="category",
        entity_id=category.id,
        action=AuditAction.CREATE.value,
        new_value={"name": category.name, "icon": category.icon},
    )
    await db.commit()
    await db.refresh(category)
    return Envelope(data=CategoryOut.model_validate(category), message="Category added.")
