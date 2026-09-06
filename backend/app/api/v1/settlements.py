from __future__ import annotations

from fastapi import APIRouter, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.core import idempotency
from app.core.deps import CurrentUser, DbSession, GroupCtx, IdempotencyKeyHeader
from app.repositories import group_repo, settlement_repo
from app.schemas.balance import SettlementCreate, SettlementOut
from app.schemas.common import Envelope, Page
from app.services import settlement_ops

router = APIRouter(tags=["settlements"])


async def _decorate(db, settlements, group_id: int) -> list[SettlementOut]:
    names = {m.user_id: u.name for m, u in await group_repo.list_members(db, group_id)}
    return [
        SettlementOut.model_validate(s).model_copy(
            update={
                "from_name": names.get(s.from_user_id),
                "to_name": names.get(s.to_user_id),
            }
        )
        for s in settlements
    ]


@router.get("/groups/{group_id}/settlements", response_model=Envelope[Page[SettlementOut]])
async def list_settlements(
    ctx: GroupCtx,
    db: DbSession,
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = None,
    include_reversed: bool = True,
):
    rows = await settlement_repo.list_for_group(
        db,
        ctx.group_id,
        limit=limit + 1,
        cursor_id=int(cursor) if cursor and cursor.isdigit() else None,
        include_reversed=include_reversed,
    )
    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = str(rows[-1].id)

    return Envelope(
        data=Page[SettlementOut](
            items=await _decorate(db, rows, ctx.group_id), next_cursor=next_cursor
        )
    )


@router.post(
    "/groups/{group_id}/settlements",
    response_model=Envelope[SettlementOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_settlement(
    payload: SettlementCreate,
    ctx: GroupCtx,
    db: DbSession,
    idempotency_key: IdempotencyKeyHeader = None,
):
    endpoint = f"POST /groups/{ctx.group_id}/settlements"
    stored = await idempotency.replay(
        db, key=idempotency_key, user_id=ctx.user.id, endpoint=endpoint
    )
    if stored is not None:
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content=stored,
            headers={"Idempotency-Replayed": "true"},
        )

    settlement = await settlement_ops.create_settlement(db, ctx, payload)
    items = await _decorate(db, [settlement], ctx.group_id)
    encoded = jsonable_encoder(
        Envelope(data=items[0], message="Settlement recorded.").model_dump(mode="json")
    )

    await idempotency.remember(
        db, key=idempotency_key, user_id=ctx.user.id, endpoint=endpoint, response_body=encoded
    )
    return JSONResponse(status_code=status.HTTP_201_CREATED, content=encoded)


@router.delete("/settlements/{settlement_id}", response_model=Envelope[SettlementOut])
async def reverse_settlement(settlement_id: int, db: DbSession, user: CurrentUser):
    settlement = await settlement_ops.reverse_settlement(db, user, settlement_id)
    items = await _decorate(db, [settlement], settlement.group_id)
    return Envelope(data=items[0], message="Settlement reversed.")
