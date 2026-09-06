from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import DbSession, GroupCtx
from app.repositories import group_repo
from app.schemas.balance import (
    BalanceOut,
    GroupBalancesOut,
    PairwiseDebtOut,
    SuggestionOut,
    SuggestionsOut,
)
from app.schemas.common import Envelope
from app.services import ledger_service
from app.services.settlement_service import suggest_settlements, summarise_for_user
from app.services.split_service import ZERO

router = APIRouter(tags=["balances"])


async def _names(db, group_id: int) -> dict[int, str]:
    return {m.user_id: u.name for m, u in await group_repo.list_members(db, group_id)}


def _pairwise_out(pairwise, names) -> list[PairwiseDebtOut]:
    return [
        PairwiseDebtOut(
            from_user_id=d.from_user_id,
            from_name=names.get(d.from_user_id, "Former member"),
            to_user_id=d.to_user_id,
            to_name=names.get(d.to_user_id, "Former member"),
            amount=d.amount,
        )
        for d in pairwise
    ]


@router.get("/groups/{group_id}/balances", response_model=Envelope[GroupBalancesOut])
async def get_balances(ctx: GroupCtx, db: DbSession):
    ledger = await ledger_service.get_ledger(db, ctx.group_id)
    names = await _names(db, ctx.group_id)
    mine = next((b for b in ledger.balances if b.user_id == ctx.user.id), None)

    return Envelope(
        data=GroupBalancesOut(
            group_id=ctx.group_id,
            currency=ctx.group.currency,
            balances=[
                BalanceOut(
                    user_id=b.user_id,
                    name=names.get(b.user_id, "Former member"),
                    total_paid=b.total_paid,
                    total_share=b.total_share,
                    settlements_paid=b.settlements_paid,
                    settlements_received=b.settlements_received,
                    balance=b.balance,
                )
                for b in ledger.balances
            ],
            pairwise=_pairwise_out(ledger.pairwise, names),
            my_balance=mine.balance if mine else ZERO,
            total_outstanding=ledger.total_outstanding,
        )
    )


@router.get(
    "/groups/{group_id}/settlement-suggestions", response_model=Envelope[SuggestionsOut]
)
async def get_suggestions(ctx: GroupCtx, db: DbSession):
    """The simplified plan and the unsimplified pairwise ledger, side by side --
    the simplified plan alone confuses people (Section 9)."""
    ledger = await ledger_service.get_ledger(db, ctx.group_id)
    names = await _names(db, ctx.group_id)
    suggestions = suggest_settlements(ledger.balances)
    you_owe, you_are_owed = summarise_for_user(ctx.user.id, suggestions)

    return Envelope(
        data=SuggestionsOut(
            group_id=ctx.group_id,
            currency=ctx.group.currency,
            suggestions=[
                SuggestionOut(
                    from_user_id=s.from_user_id,
                    from_name=names.get(s.from_user_id, "Former member"),
                    to_user_id=s.to_user_id,
                    to_name=names.get(s.to_user_id, "Former member"),
                    amount=s.amount,
                )
                for s in suggestions
            ],
            pairwise=_pairwise_out(ledger.pairwise, names),
            you_owe=you_owe,
            you_are_owed=you_are_owed,
        )
    )
