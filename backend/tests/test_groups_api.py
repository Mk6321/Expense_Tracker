from __future__ import annotations

from tests.conftest import data_of, join


async def test_creator_becomes_admin(alice, group):
    assert group["role"] == "admin"
    members = data_of(await alice.get(f"/api/v1/groups/{group['id']}/members"))
    assert len(members) == 1
    assert members[0]["role"] == "admin"


async def test_invite_and_join(alice, bob, group):
    invite = data_of(await alice.post(f"/api/v1/groups/{group['id']}/invites"))
    assert len(invite["code"]) == 8

    joined = data_of(await bob.post("/api/v1/groups/join", json={"invite_code": invite["code"]}))
    assert joined["id"] == group["id"]

    members = data_of(await alice.get(f"/api/v1/groups/{group['id']}/members"))
    assert {m["role"] for m in members} == {"admin", "member"}


async def test_invite_code_is_case_insensitive(alice, bob, group):
    invite = data_of(await alice.post(f"/api/v1/groups/{group['id']}/invites"))
    response = await bob.post(
        "/api/v1/groups/join", json={"invite_code": invite["code"].lower()}
    )
    assert response.status_code == 200


async def test_bad_invite_codes_are_rejected(bob, alice, group):
    unknown = await bob.post("/api/v1/groups/join", json={"invite_code": "ZZZZZZZZ"})
    assert unknown.status_code == 404
    assert unknown.json()["error_code"] == "INVITE_INVALID"

    invite = data_of(await alice.post(f"/api/v1/groups/{group['id']}/invites"))
    await alice.delete(f"/api/v1/groups/{group['id']}/invites/{invite['code']}")
    revoked = await bob.post("/api/v1/groups/join", json={"invite_code": invite["code"]})
    assert revoked.status_code == 422
    assert revoked.json()["error_code"] == "INVITE_REVOKED"


async def test_joining_twice_is_rejected(alice, bob, group):
    await join(alice, group["id"], bob)
    invite = data_of(await alice.post(f"/api/v1/groups/{group['id']}/invites"))
    again = await bob.post("/api/v1/groups/join", json={"invite_code": invite["code"]})
    assert again.status_code == 409
    assert again.json()["error_code"] == "ALREADY_MEMBER"


class TestCrossGroupIsolation:
    """Section 1: a valid id from someone else's group must be indistinguishable
    from an id that does not exist -- 404 everywhere, never 403."""

    async def test_outsider_gets_404_on_every_group_route(self, bob, group):
        group_id = group["id"]
        for path in (
            f"/api/v1/groups/{group_id}",
            f"/api/v1/groups/{group_id}/members",
            f"/api/v1/groups/{group_id}/expenses",
            f"/api/v1/groups/{group_id}/balances",
            f"/api/v1/groups/{group_id}/settlements",
            f"/api/v1/groups/{group_id}/settlement-suggestions",
            f"/api/v1/groups/{group_id}/categories",
            f"/api/v1/groups/{group_id}/reports/summary",
            f"/api/v1/groups/{group_id}/reports/categories",
            f"/api/v1/groups/{group_id}/reports/members",
            f"/api/v1/groups/{group_id}/reports/monthly",
        ):
            response = await bob.get(path)
            assert response.status_code == 404, path
            assert response.json()["error_code"] == "GROUP_ACCESS_DENIED", path

    async def test_a_real_group_and_a_missing_group_look_identical(self, bob, group):
        real = await bob.get(f"/api/v1/groups/{group['id']}")
        missing = await bob.get("/api/v1/groups/999999")
        assert real.status_code == missing.status_code == 404
        assert real.json() == missing.json()

    async def test_outsider_cannot_write(self, bob, group):
        response = await bob.post(
            f"/api/v1/groups/{group['id']}/expenses",
            json={
                "description": "Sneaky",
                "amount": "10.00",
                "expense_date": "2026-01-01",
                "split_type": "equal",
                "paid_by": bob.id,
                "participants": [{"user_id": bob.id}],
            },
        )
        assert response.status_code == 404

    async def test_removed_member_loses_access(self, alice, bob, group):
        await join(alice, group["id"], bob)
        assert (await bob.get(f"/api/v1/groups/{group['id']}")).status_code == 200

        await alice.delete(f"/api/v1/groups/{group['id']}/members/{bob.id}")
        assert (await bob.get(f"/api/v1/groups/{group['id']}")).status_code == 404


class TestRoles:
    async def test_member_cannot_do_admin_things(self, alice, bob, group):
        await join(alice, group["id"], bob)
        response = await bob.post(f"/api/v1/groups/{group['id']}/invites")
        assert response.status_code == 403
        assert response.json()["error_code"] == "ADMIN_REQUIRED"

    async def test_viewer_cannot_write(self, alice, bob, group):
        await join(alice, group["id"], bob)
        await alice.put(
            f"/api/v1/groups/{group['id']}/members/{bob.id}/role", json={"role": "viewer"}
        )
        response = await bob.post(
            f"/api/v1/groups/{group['id']}/expenses",
            json={
                "description": "Nope",
                "amount": "10.00",
                "expense_date": "2026-01-01",
                "split_type": "equal",
                "paid_by": bob.id,
                "participants": [{"user_id": bob.id}],
            },
        )
        assert response.status_code == 403
        assert response.json()["error_code"] == "READ_ONLY_ROLE"
        # ...but reading still works.
        assert (await bob.get(f"/api/v1/groups/{group['id']}/balances")).status_code == 200

    async def test_last_admin_cannot_be_demoted(self, alice, group):
        response = await alice.put(
            f"/api/v1/groups/{group['id']}/members/{alice.id}/role", json={"role": "member"}
        )
        assert response.status_code == 422
        assert response.json()["error_code"] == "LAST_ADMIN"


class TestMemberRemoval:
    async def test_blocked_while_the_balance_is_non_zero(self, alice, bob, group):
        await join(alice, group["id"], bob)
        await alice.post(
            f"/api/v1/groups/{group['id']}/expenses",
            json={
                "description": "Pizza",
                "amount": "100.00",
                "expense_date": "2026-01-01",
                "split_type": "equal",
                "paid_by": alice.id,
                "participants": [{"user_id": alice.id}, {"user_id": bob.id}],
            },
        )
        response = await alice.delete(f"/api/v1/groups/{group['id']}/members/{bob.id}")
        assert response.status_code == 409
        assert response.json()["error_code"] == "MEMBER_HAS_BALANCE"

    async def test_force_removal_keeps_the_row_and_the_history(self, alice, bob, group):
        await join(alice, group["id"], bob)
        await alice.post(
            f"/api/v1/groups/{group['id']}/expenses",
            json={
                "description": "Pizza",
                "amount": "100.00",
                "expense_date": "2026-01-01",
                "split_type": "equal",
                "paid_by": alice.id,
                "participants": [{"user_id": alice.id}, {"user_id": bob.id}],
            },
        )
        removed = data_of(
            await alice.delete(f"/api/v1/groups/{group['id']}/members/{bob.id}?force=true")
        )
        assert removed["status"] == "removed"
        assert removed["outstanding_balance"] == "-50.00"

        # The membership row survives, so the old split still resolves to a name.
        members = data_of(await alice.get(f"/api/v1/groups/{group['id']}/members"))
        assert any(m["user_id"] == bob.id and m["status"] == "removed" for m in members)

        balances = data_of(await alice.get(f"/api/v1/groups/{group['id']}/balances"))
        assert any(b["user_id"] == bob.id for b in balances["balances"])


async def test_archive_is_not_a_delete(alice, group):
    archived = data_of(await alice.delete(f"/api/v1/groups/{group['id']}"))
    assert archived["is_archived"] is True
    # Still readable -- history is preserved.
    assert (await alice.get(f"/api/v1/groups/{group['id']}")).status_code == 200


async def test_archived_group_rejects_new_expenses(alice, group):
    await alice.delete(f"/api/v1/groups/{group['id']}")
    response = await alice.post(
        f"/api/v1/groups/{group['id']}/expenses",
        json={
            "description": "Too late",
            "amount": "10.00",
            "expense_date": "2026-01-01",
            "split_type": "equal",
            "paid_by": alice.id,
            "participants": [{"user_id": alice.id}],
        },
    )
    assert response.status_code == 403
    assert response.json()["error_code"] == "GROUP_ARCHIVED"


async def test_group_list_only_shows_your_own_groups(alice, bob, group):
    assert len(data_of(await alice.get("/api/v1/groups"))) == 1
    assert data_of(await bob.get("/api/v1/groups")) == []
