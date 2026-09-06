from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.core import idempotency
from app.core.deps import CurrentUser, DbSession, GroupCtx, IdempotencyKeyHeader
from app.models import Expense
from app.repositories import category_repo, expense_repo, group_repo
from app.schemas.common import Envelope, Page
from app.schemas.expense import ExpenseCreate, ExpenseOut, ExpenseUpdate
from app.services import expense_service

router = APIRouter(tags=["expenses"])


async def _decorate(db, expenses: list[Expense], group_id: int, viewer_id: int):
    """Attach payer/category names so the list view is one request, not N+1."""
    members = {m.user_id: u.name for m, u in await group_repo.list_members(db, group_id)}
    categories = {c.id: c.name for c in await category_repo.list_for_group(db, group_id)}
    return [
        ExpenseOut.model_validate(e).model_copy(
            update={
                "paid_by_name": members.get(e.paid_by),
                "category_name": categories.get(e.category_id) if e.category_id else None,
                "my_share": expense_service.my_share(e, viewer_id),
            }
        )
        for e in expenses
    ]


@router.get("/groups/{group_id}/expenses", response_model=Envelope[Page[ExpenseOut]])
async def list_expenses(
    ctx: GroupCtx,
    db: DbSession,
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = None,
    include_reversed: bool = True,
    category_id: int | None = None,
    paid_by: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    expenses = await expense_repo.list_for_group(
        db,
        ctx.group_id,
        limit=limit + 1,  # one extra row tells us whether another page exists
        cursor_id=int(cursor) if cursor and cursor.isdigit() else None,
        include_reversed=include_reversed,
        category_id=category_id,
        paid_by=paid_by,
        date_from=date_from,
        date_to=date_to,
    )
    next_cursor = None
    if len(expenses) > limit:
        expenses = expenses[:limit]
        next_cursor = str(expenses[-1].id)

    items = await _decorate(db, expenses, ctx.group_id, ctx.user.id)
    return Envelope(data=Page[ExpenseOut](items=items, next_cursor=next_cursor))


@router.post(
    "/groups/{group_id}/expenses",
    response_model=Envelope[ExpenseOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_expense(
    payload: ExpenseCreate,
    ctx: GroupCtx,
    db: DbSession,
    response: Response,
    idempotency_key: IdempotencyKeyHeader = None,
):
    endpoint = f"POST /groups/{ctx.group_id}/expenses"
    stored = await idempotency.replay(
        db, key=idempotency_key, user_id=ctx.user.id, endpoint=endpoint
    )
    if stored is not None:
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content=stored,
            headers={"Idempotency-Replayed": "true"},
        )

    expense = await expense_service.create_expense(db, ctx, payload)
    items = await _decorate(db, [expense], ctx.group_id, ctx.user.id)
    body = Envelope(data=items[0], message="Expense added.")
    encoded = jsonable_encoder(body.model_dump(mode="json"))

    await idempotency.remember(
        db,
        key=idempotency_key,
        user_id=ctx.user.id,
        endpoint=endpoint,
        response_body=encoded,
    )
    return JSONResponse(status_code=status.HTTP_201_CREATED, content=encoded)


@router.get("/expenses/{expense_id}", response_model=Envelope[ExpenseOut])
async def get_expense(expense_id: int, db: DbSession, user: CurrentUser):
    expense, _role = await expense_service.get_expense(db, user, expense_id)
    items = await _decorate(db, [expense], expense.group_id, user.id)
    return Envelope(data=items[0])


@router.put("/expenses/{expense_id}", response_model=Envelope[ExpenseOut])
async def update_expense(
    expense_id: int, payload: ExpenseUpdate, db: DbSession, user: CurrentUser
):
    expense = await expense_service.update_expense(db, user, expense_id, payload)
    items = await _decorate(db, [expense], expense.group_id, user.id)
    return Envelope(data=items[0], message="Expense updated.")


@router.delete("/expenses/{expense_id}", response_model=Envelope[ExpenseOut])
async def reverse_expense(expense_id: int, db: DbSession, user: CurrentUser):
    expense = await expense_service.reverse_expense(db, user, expense_id)
    items = await _decorate(db, [expense], expense.group_id, user.id)
    return Envelope(data=items[0], message="Expense reversed.")
