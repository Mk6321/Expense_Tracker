from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUser, DbSession, GroupCtx
from app.schemas.common import Envelope
from app.schemas.group import (
    GroupCreate,
    GroupOut,
    GroupUpdate,
    InviteOut,
    JoinRequest,
    MemberOut,
    RemoveMemberResult,
    RoleUpdate,
)
from app.services import group_service, ledger_service

router = APIRouter(tags=["groups"])


@router.get("/groups", response_model=Envelope[list[GroupOut]])
async def list_groups(db: DbSession, user: CurrentUser):
    rows = await group_service.list_groups(db, user)
    out = []
    for group, role, member_count in rows:
        balance = await ledger_service.get_user_balance(db, group.id, user.id)
        out.append(
            GroupOut.model_validate(group).model_copy(
                update={"role": role, "member_count": member_count, "my_balance": balance}
            )
        )
    return Envelope(data=out)


@router.post("/groups", response_model=Envelope[GroupOut], status_code=status.HTTP_201_CREATED)
async def create_group(payload: GroupCreate, db: DbSession, user: CurrentUser):
    group = await group_service.create_group(
        db, user=user, name=payload.name, currency=payload.currency
    )
    return Envelope(
        data=GroupOut.model_validate(group).model_copy(
            update={"role": "admin", "member_count": 1, "my_balance": None}
        ),
        message="Group created.",
    )


# Declared before /groups/{group_id} so "join" is not swallowed as a group id.
@router.post("/groups/join", response_model=Envelope[GroupOut])
async def join_group(payload: JoinRequest, db: DbSession, user: CurrentUser):
    group = await group_service.join_group(db, user=user, invite_code=payload.invite_code)
    return Envelope(data=GroupOut.model_validate(group), message=f"Joined {group.name}.")


@router.get("/groups/{group_id}", response_model=Envelope[GroupOut])
async def get_group(ctx: GroupCtx, db: DbSession):
    members = await group_service.list_members(db, ctx)
    active = [m for m, _ in members if m.status == "active"]
    balance = await ledger_service.get_user_balance(db, ctx.group_id, ctx.user.id)
    return Envelope(
        data=GroupOut.model_validate(ctx.group).model_copy(
            update={"role": ctx.role, "member_count": len(active), "my_balance": balance}
        )
    )


@router.put("/groups/{group_id}", response_model=Envelope[GroupOut])
async def update_group(payload: GroupUpdate, ctx: GroupCtx, db: DbSession):
    group = await group_service.update_group(
        db, ctx, name=payload.name, currency=payload.currency
    )
    return Envelope(data=GroupOut.model_validate(group), message="Group updated.")


@router.delete("/groups/{group_id}", response_model=Envelope[GroupOut])
async def archive_group(ctx: GroupCtx, db: DbSession):
    group = await group_service.archive_group(db, ctx)
    return Envelope(data=GroupOut.model_validate(group), message="Group archived.")


@router.post("/groups/{group_id}/invites", response_model=Envelope[InviteOut],
             status_code=status.HTTP_201_CREATED)
async def create_invite(ctx: GroupCtx, db: DbSession):
    invite = await group_service.create_invite(db, ctx)
    return Envelope(
        data=InviteOut(
            code=invite.code,
            group_id=invite.group_id,
            expires_at=invite.expires_at,
            is_revoked=invite.is_revoked,
        ),
        message="Invite code created.",
    )


@router.delete("/groups/{group_id}/invites/{code}", response_model=Envelope[InviteOut])
async def revoke_invite(code: str, ctx: GroupCtx, db: DbSession):
    invite = await group_service.revoke_invite(db, ctx, code)
    return Envelope(
        data=InviteOut(
            code=invite.code,
            group_id=invite.group_id,
            expires_at=invite.expires_at,
            is_revoked=invite.is_revoked,
        ),
        message="Invite revoked.",
    )


@router.get("/groups/{group_id}/members", response_model=Envelope[list[MemberOut]])
async def list_members(ctx: GroupCtx, db: DbSession):
    rows = await group_service.list_members(db, ctx)
    return Envelope(
        data=[
            MemberOut(
                user_id=member.user_id,
                name=user.name,
                email=user.email,
                role=member.role,
                status=member.status,
                joined_at=member.joined_at,
            )
            for member, user in rows
        ]
    )


@router.put("/groups/{group_id}/members/{user_id}/role", response_model=Envelope[MemberOut])
async def change_role(user_id: int, payload: RoleUpdate, ctx: GroupCtx, db: DbSession):
    member = await group_service.change_role(
        db, ctx, target_user_id=user_id, role=payload.role.value
    )
    rows = await group_service.list_members(db, ctx)
    user = next(u for m, u in rows if m.user_id == user_id)
    return Envelope(
        data=MemberOut(
            user_id=member.user_id,
            name=user.name,
            email=user.email,
            role=member.role,
            status=member.status,
            joined_at=member.joined_at,
        ),
        message="Role updated.",
    )


@router.delete("/groups/{group_id}/members/{user_id}",
               response_model=Envelope[RemoveMemberResult])
async def remove_member(
    user_id: int,
    ctx: GroupCtx,
    db: DbSession,
    force: bool = Query(False, description="Remove even with a non-zero balance."),
):
    member, balance = await group_service.remove_member(
        db, ctx, target_user_id=user_id, force=force
    )
    return Envelope(
        data=RemoveMemberResult(
            user_id=member.user_id,
            status=member.status,
            forced=force,
            outstanding_balance=balance,
        ),
        message="Member removed.",
    )
