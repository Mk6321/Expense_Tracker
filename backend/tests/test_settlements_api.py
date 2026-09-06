from __future__ import annotations

import pytest_asyncio

from tests.conftest import data_of, join


@pytest_asyncio.fixture
async def trio(alice, bob, group, make_user):
    """Alice, Bob and Cara in one group, with a 300 expense split three ways."""
    cara = await make_user("Cara")
    await join(alice, group["id"], bob)
    await join(alice, group["id"], cara)
    await alice.post(
        f"/api/v1/groups/{group['id']}/expenses",
        json={
            "description": "Weekend rental",
            "amount": "300.00",
            "expense_date": "2026-02-01",
            "split_type": "equal",
            "paid_by": alice.id,
            "participants": [
                {"user_id": alice.id},
                {"user_id": bob.id},
                {"user_id": cara.id},
            ],
        },
    )
    return {"group": group, "cara": cara}


async def test_balances_reflect_the_expense(alice, bob, trio):
    group_id = trio["group"]["id"]
    balances = data_of(await alice.get(f"/api/v1/groups/{group_id}/balances"))
    by_user = {b["user_id"]: b["balance"] for b in balances["balances"]}

    assert by_user[alice.id] == "200.00"
    assert by_user[bob.id] == "-100.00"
    assert balances["my_balance"] == "200.00"
    assert balances["total_outstanding"] == "200.00"


async def test_suggestions_include_the_unsimplified_ledger(alice, bob, trio):
    """Section 9 -- the simplified plan is shown alongside the real pairwise debts."""
    group_id = trio["group"]["id"]
    payload = data_of(await bob.get(f"/api/v1/groups/{group_id}/settlement-suggestions"))

    assert payload["you_owe"] == "100.00"
    assert payload["you_are_owed"] == "0.00"
    assert len(payload["suggestions"]) == 2
    assert all(s["to_user_id"] == alice.id for s in payload["suggestions"])
    assert payload["suggestions"][0]["to_name"] == alice.name
    assert len(payload["pairwise"]) == 2


async def test_recording_a_settlement_clears_the_balance(alice, bob, trio):
    group_id = trio["group"]["id"]
    created = data_of(
        await bob.post(
            f"/api/v1/groups/{group_id}/settlements",
            json={
                "from_user_id": bob.id,
                "to_user_id": alice.id,
                "amount": "100.00",
                "settlement_date": "2026-02-05",
            },
        )
    )
    assert created["amount"] == "100.00"
    assert created["from_name"] == bob.name

    balances = data_of(await alice.get(f"/api/v1/groups/{group_id}/balances"))
    by_user = {b["user_id"]: b["balance"] for b in balances["balances"]}
    assert by_user[bob.id] == "0.00"
    assert by_user[alice.id] == "100.00"


async def test_settlement_does_not_touch_expense_rows(alice, bob, trio):
    group_id = trio["group"]["id"]
    before = data_of(await alice.get(f"/api/v1/groups/{group_id}/expenses"))["items"][0]
    await bob.post(
        f"/api/v1/groups/{group_id}/settlements",
        json={
            "from_user_id": bob.id,
            "to_user_id": alice.id,
            "amount": "100.00",
            "settlement_date": "2026-02-05",
        },
    )
    after = data_of(await alice.get(f"/api/v1/groups/{group_id}/expenses"))["items"][0]
    assert before == after


async def test_reversing_a_settlement_restores_the_balance(alice, bob, trio):
    group_id = trio["group"]["id"]
    created = data_of(
        await bob.post(
            f"/api/v1/groups/{group_id}/settlements",
            json={
                "from_user_id": bob.id,
                "to_user_id": alice.id,
                "amount": "100.00",
                "settlement_date": "2026-02-05",
            },
        )
    )
    reversed_row = data_of(await bob.delete(f"/api/v1/settlements/{created['id']}"))
    assert reversed_row["is_reversed"] is True

    balances = data_of(await alice.get(f"/api/v1/groups/{group_id}/balances"))
    by_user = {b["user_id"]: b["balance"] for b in balances["balances"]}
    assert by_user[bob.id] == "-100.00"

    # The row is still there, just excluded from the maths.
    listed = data_of(await alice.get(f"/api/v1/groups/{group_id}/settlements"))
    assert len(listed["items"]) == 1


async def test_multiple_settlements_net_out_to_zero(alice, bob, trio):
    group_id = trio["group"]["id"]
    cara = trio["cara"]
    for payer in (bob, cara):
        await payer.post(
            f"/api/v1/groups/{group_id}/settlements",
            json={
                "from_user_id": payer.id,
                "to_user_id": alice.id,
                "amount": "100.00",
                "settlement_date": "2026-02-05",
            },
        )
    balances = data_of(await alice.get(f"/api/v1/groups/{group_id}/balances"))
    assert all(b["balance"] == "0.00" for b in balances["balances"])

    suggestions = data_of(await alice.get(f"/api/v1/groups/{group_id}/settlement-suggestions"))
    assert suggestions["suggestions"] == []
    assert suggestions["pairwise"] == []


async def test_settlement_idempotency_key_is_honoured(alice, bob, trio):
    group_id = trio["group"]["id"]
    payload = {
        "from_user_id": bob.id,
        "to_user_id": alice.id,
        "amount": "100.00",
        "settlement_date": "2026-02-05",
    }
    headers = {"Idempotency-Key": "settle-once"}
    first = await bob.post(
        f"/api/v1/groups/{group_id}/settlements", json=payload, headers=headers
    )
    second = await bob.post(
        f"/api/v1/groups/{group_id}/settlements", json=payload, headers=headers
    )
    assert first.json()["data"]["id"] == second.json()["data"]["id"]

    listed = data_of(await alice.get(f"/api/v1/groups/{group_id}/settlements"))
    assert len(listed["items"]) == 1


async def test_a_member_cannot_invent_a_settlement_between_other_people(alice, bob, trio):
    group_id = trio["group"]["id"]
    cara = trio["cara"]
    response = await bob.post(
        f"/api/v1/groups/{group_id}/settlements",
        json={
            "from_user_id": cara.id,
            "to_user_id": alice.id,
            "amount": "100.00",
            "settlement_date": "2026-02-05",
        },
    )
    assert response.status_code == 403
    assert response.json()["error_code"] == "NOT_SETTLEMENT_PARTY"


async def test_admin_can_record_on_behalf_of_others(alice, trio):
    group_id = trio["group"]["id"]
    cara = trio["cara"]
    response = await alice.post(
        f"/api/v1/groups/{group_id}/settlements",
        json={
            "from_user_id": cara.id,
            "to_user_id": alice.id,
            "amount": "100.00",
            "settlement_date": "2026-02-05",
        },
    )
    assert response.status_code == 201


async def test_self_settlement_is_rejected(alice, trio):
    group_id = trio["group"]["id"]
    response = await alice.post(
        f"/api/v1/groups/{group_id}/settlements",
        json={
            "from_user_id": alice.id,
            "to_user_id": alice.id,
            "amount": "10.00",
            "settlement_date": "2026-02-05",
        },
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "SAME_PARTY"


async def test_outsider_cannot_reverse_a_settlement(alice, bob, trio, make_user):
    group_id = trio["group"]["id"]
    stranger = await make_user("Stranger")
    created = data_of(
        await bob.post(
            f"/api/v1/groups/{group_id}/settlements",
            json={
                "from_user_id": bob.id,
                "to_user_id": alice.id,
                "amount": "100.00",
                "settlement_date": "2026-02-05",
            },
        )
    )
    response = await stranger.delete(f"/api/v1/settlements/{created['id']}")
    assert response.status_code == 404
