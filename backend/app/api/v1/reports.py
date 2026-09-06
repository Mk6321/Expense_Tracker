from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import DbSession, GroupCtx
from app.schemas.common import Envelope
from app.schemas.report import (
    CategoryReportRow,
    MemberReportRow,
    MonthlyReportRow,
    SummaryOut,
)
from app.services import report_service

router = APIRouter(prefix="/groups/{group_id}/reports", tags=["reports"])


@router.get("/summary", response_model=Envelope[SummaryOut])
async def summary(ctx: GroupCtx, db: DbSession):
    return Envelope(data=await report_service.summary(db, ctx))


@router.get("/categories", response_model=Envelope[list[CategoryReportRow]])
async def by_category(ctx: GroupCtx, db: DbSession):
    return Envelope(data=await report_service.by_category(db, ctx))


@router.get("/members", response_model=Envelope[list[MemberReportRow]])
async def by_member(ctx: GroupCtx, db: DbSession):
    return Envelope(data=await report_service.by_member(db, ctx))


@router.get("/monthly", response_model=Envelope[list[MonthlyReportRow]])
async def monthly(ctx: GroupCtx, db: DbSession):
    return Envelope(data=await report_service.monthly(db, ctx))
