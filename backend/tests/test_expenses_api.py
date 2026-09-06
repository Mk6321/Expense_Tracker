from __future__ import annotations

import pytest_asyncio

from tests.conftest import data_of, join


def expense_payload(paid_by: int, member_ids: list[int] = (), **overrides) -> dict:
    payload = {
        "description": "Dinner",
        "amount": "100.00",
        "expense_date": "2026-01-15",
        "split_type": "equal",
        "paid_by": paid_by,
        "participants": [{"user_id": uid} for uid in member_ids],
    }
    payload.update(overrides)
    return payload


@pytest_asyncio.fixture
async def flat(alice, bob, group):
    """A group with two members and a helper for the expenses URL."""
    await join(alice, group["id"], bob)
    return group


class TestCreate:
    async def test_equal_split_is_computed_server_side(self, alice, bob, flat):
        created = data_of(
            await alice.post(
                f"/api/v1/groups/{flat['id']}/expenses",
                json=expense_payload(alice.id, [alice.id, bob.id]),
            )
        )
        assert created["amount"] == "100.00"
        assert sorted(s["amount"] for s in created["splits"]) == ["50.00", "50.00"]
        assert created["version"] == 1
        assert created["is_reversed"] is False

    async def test_money_is_serialised_as_a_string_not_a_number(self, alice, bob, flat):
        response = await alice.post(
            f"/api/v1/groups/{flat['id']}/expenses",
            json=expense_payload(alice.id, [alice.id, bob.id]),
        )
        raw = response.json()["data"]
        assert isinstance(raw["amount"], str)
        assert all(isinstance(s["amount"], str) for s in raw["splits"])
        # No bare JSON number for the amount anywhere in the payload.
        assert '"amount": 100' not in response.text

    async def test_client_supplied_amounts_are_ignored_for_an_equal_split(
        self, alice, bob, flat
    ):
        """A malicious client sends a lopsided split with split_type=equal; the
        server recomputes it regardless of what arrived."""
        payload = expense_payload(alice.id, [alice.id, bob.id])
        payload["participants"] = [
            {"user_id": alice.id, "amount": "1.00"},
            {"user_id": bob.id, "amount": "99.00"},
        ]
        created = data_of(
            await alice.post(f"/api/v1/groups/{flat['id']}/expenses", json=payload)
        )
        assert sorted(s["amount"] for s in created["splits"]) == ["50.00", "50.00"]

    async def test_exact_split_must_sum_to_the_total(self, alice, bob, flat):
        payload = expense_payload(
            alice.id,
            split_type="exact",
            participants=[
                {"user_id": alice.id, "amount": "60.00"},
                {"user_id": bob.id, "amount": "30.00"},
            ],
        )
        response = await alice.post(f"/api/v1/groups/{flat['id']}/expenses", json=payload)
        assert response.status_code == 422
        assert response.json()["error_code"] == "SPLIT_SUM_MISMATCH"

    async def test_percentage_split(self, alice, bob, flat):
        payload = expense_payload(
            alice.id,
            split_type="percentage",
            participants=[
                {"user_id": alice.id, "percentage": "70"},
                {"user_id": bob.id, "percentage": "30"},
            ],
        )
        created = data_of(
            await alice.post(f"/api/v1/groups/{flat['id']}/expenses", json=payload)
        )
        by_user = {s["user_id"]: s["amount"] for s in created["splits"]}
        assert by_user[alice.id] == "70.00"
        assert by_user[bob.id] == "30.00"

    async def test_shares_split(self, alice, bob, flat):
        payload = expense_payload(
            alice.id,
            amount="90.00",
            split_type="shares",
            participants=[
                {"user_id": alice.id, "shares": "2"},
                {"user_id": bob.id, "shares": "1"},
            ],
        )
        created = data_of(
            await alice.post(f"/api/v1/groups/{flat['id']}/expenses", json=payload)
        )
        by_user = {s["user_id"]: s["amount"] for s in created["splits"]}
        assert by_user[alice.id] == "60.00"
        assert by_user[bob.id] == "30.00"

    async def test_outsider_cannot_be_added_as_a_participant(self, alice, bob, group, make_user):
        stranger = await make_user("Stranger")
        response = await alice.post(
            f"/api/v1/groups/{group['id']}/expenses",
            json=expense_payload(alice.id, [alice.id, stranger.id]),
        )
        assert response.status_code == 422
        assert response.json()["error_code"] == "PARTICIPANT_NOT_MEMBER"

    async def test_zero_amount_is_rejected(self, alice, flat):
        response = await alice.post(
            f"/api/v1/groups/{flat['id']}/expenses",
            json=expense_payload(alice.id, [alice.id], amount="0.00"),
        )
        assert response.status_code == 422


class TestIdempotency:
    async def test_replaying_a_key_does_not_create_a_second_expense(self, alice, bob, flat):
        payload = expense_payload(alice.id, [alice.id, bob.id])
        headers = {"Idempotency-Key": "retry-me-once"}

        first = await alice.post(
            f"/api/v1/groups/{flat['id']}/expenses", json=payload, headers=headers
        )
        second = await alice.post(
            f"/api/v1/groups/{flat['id']}/expenses", json=payload, headers=headers
        )

        assert first.status_code == second.status_code == 201
        assert first.json()["data"]["id"] == second.json()["data"]["id"]
        assert second.headers.get("Idempotency-Replayed") == "true"

        listed = data_of(await alice.get(f"/api/v1/groups/{flat['id']}/expenses"))
        assert len(listed["items"]) == 1

    async def test_different_keys_create_different_expenses(self, alice, bob, flat):
        payload = expense_payload(alice.id, [alice.id, bob.id])
        await alice.post(
            f"/api/v1/groups/{flat['id']}/expenses",
            json=payload,
            headers={"Idempotency-Key": "one"},
        )
        await alice.post(
            f"/api/v1/groups/{flat['id']}/expenses",
            json=payload,
            headers={"Idempotency-Key": "two"},
        )
        listed = data_of(await alice.get(f"/api/v1/groups/{flat['id']}/expenses"))
        assert len(listed["items"]) == 2

    async def test_a_key_is_scoped_to_its_user(self, alice, bob, flat):
        payload = expense_payload(bob.id, [alice.id, bob.id])
        headers = {"Idempotency-Key": "shared-key"}
        await alice.post(
            f"/api/v1/groups/{flat['id']}/expenses", json=payload, headers=headers
        )
        response = await bob.post(
            f"/api/v1/groups/{flat['id']}/expenses", json=payload, headers=headers
        )
        assert response.headers.get("Idempotency-Replayed") is None
        listed = data_of(await alice.get(f"/api/v1/groups/{flat['id']}/expenses"))
        assert len(listed["items"]) == 2


class TestUpdate:
    async def test_update_bumps_the_version_and_rewrites_splits(self, alice, bob, flat):
        created = data_of(
            await alice.post(
                f"/api/v1/groups/{flat['id']}/expenses",
                json=expense_payload(alice.id, [alice.id, bob.id]),
            )
        )
        payload = expense_payload(alice.id, [alice.id, bob.id], amount="150.00")
        payload["version"] = created["version"]

        updated = data_of(await alice.put(f"/api/v1/expenses/{created['id']}", json=payload))
        assert updated["amount"] == "150.00"
        assert updated["version"] == 2
        assert sorted(s["amount"] for s in updated["splits"]) == ["75.00", "75.00"]

    async def test_stale_version_is_a_409(self, alice, bob, flat):
        """Two people open the same expense; the second save must not win silently."""
        created = data_of(
            await alice.post(
                f"/api/v1/groups/{flat['id']}/expenses",
                json=expense_payload(alice.id, [alice.id, bob.id]),
            )
        )
        stale_version = created["version"]

        first = expense_payload(alice.id, [alice.id, bob.id], amount="120.00")
        first["version"] = stale_version
        assert (await alice.put(f"/api/v1/expenses/{created['id']}", json=first)).status_code == 200

        second = expense_payload(alice.id, [alice.id, bob.id], amount="130.00")
        second["version"] = stale_version
        conflict = await alice.put(f"/api/v1/expenses/{created['id']}", json=second)
        assert conflict.status_code == 409
        assert conflict.json()["error_code"] == "VERSION_CONFLICT"

        # The losing edit did not land.
        current = data_of(await alice.get(f"/api/v1/expenses/{created['id']}"))
        assert current["amount"] == "120.00"

    async def test_member_cannot_edit_someone_elses_expense(self, alice, bob, flat):
        created = data_of(
            await alice.post(
                f"/api/v1/groups/{flat['id']}/expenses",
                json=expense_payload(alice.id, [alice.id, bob.id]),
            )
        )
        payload = expense_payload(alice.id, [alice.id, bob.id], amount="1.00")
        payload["version"] = created["version"]
        response = await bob.put(f"/api/v1/expenses/{created['id']}", json=payload)
        assert response.status_code == 403
        assert response.json()["error_code"] == "NOT_EXPENSE_OWNER"

    async def test_admin_can_edit_anyones_expense(self, alice, bob, flat):
        created = data_of(
            await bob.post(
                f"/api/v1/groups/{flat['id']}/expenses",
                json=expense_payload(bob.id, [alice.id, bob.id]),
            )
        )
        payload = expense_payload(bob.id, [alice.id, bob.id], amount="20.00")
        payload["version"] = created["version"]
        assert (await alice.put(f"/api/v1/expenses/{created['id']}", json=payload)).status_code == 200


class TestReversal:
    async def test_reverse_is_a_soft_delete(self, alice, bob, flat):
        created = data_of(
            await alice.post(
                f"/api/v1/groups/{flat['id']}/expenses",
                json=expense_payload(alice.id, [alice.id, bob.id]),
            )
        )
        reversed_expense = data_of(await alice.delete(f"/api/v1/expenses/{created['id']}"))
        assert reversed_expense["is_reversed"] is True
        assert reversed_expense["reversed_by"] == alice.id
        assert reversed_expense["reversed_at"] is not None

        # Still fetchable, and its splits are intact -- the audit trail survives.
        still_there = data_of(await alice.get(f"/api/v1/expenses/{created['id']}"))
        assert len(still_there["splits"]) == 2

    async def test_reversed_expense_is_excluded_from_balances(self, alice, bob, flat):
        created = data_of(
            await alice.post(
                f"/api/v1/groups/{flat['id']}/expenses",
                json=expense_payload(alice.id, [alice.id, bob.id]),
            )
        )
        before = data_of(await alice.get(f"/api/v1/groups/{flat['id']}/balances"))
        assert before["my_balance"] == "50.00"

        await alice.delete(f"/api/v1/expenses/{created['id']}")
        after = data_of(await alice.get(f"/api/v1/groups/{flat['id']}/balances"))
        assert after["my_balance"] == "0.00"
        assert after["pairwise"] == []

    async def test_double_reversal_is_rejected(self, alice, bob, flat):
        created = data_of(
            await alice.post(
                f"/api/v1/groups/{flat['id']}/expenses",
                json=expense_payload(alice.id, [alice.id, bob.id]),
            )
        )
        await alice.delete(f"/api/v1/expenses/{created['id']}")
        again = await alice.delete(f"/api/v1/expenses/{created['id']}")
        assert again.status_code == 422
        assert again.json()["error_code"] == "ALREADY_REVERSED"

    async def test_reversed_expense_cannot_be_edited(self, alice, bob, flat):
        created = data_of(
            await alice.post(
                f"/api/v1/groups/{flat['id']}/expenses",
                json=expense_payload(alice.id, [alice.id, bob.id]),
            )
        )
        await alice.delete(f"/api/v1/expenses/{created['id']}")
        payload = expense_payload(alice.id, [alice.id, bob.id])
        payload["version"] = created["version"]
        response = await alice.put(f"/api/v1/expenses/{created['id']}", json=payload)
        assert response.status_code == 422


class TestListing:
    async def test_expense_detail_is_404_for_an_outsider(self, alice, bob, group, make_user):
        stranger = await make_user("Stranger")
        created = data_of(
            await alice.post(
                f"/api/v1/groups/{group['id']}/expenses",
                json=expense_payload(alice.id, [alice.id]),
            )
        )
        response = await stranger.get(f"/api/v1/expenses/{created['id']}")
        assert response.status_code == 404
        assert response.json()["error_code"] == "GROUP_ACCESS_DENIED"

    async def test_pagination_returns_a_cursor(self, alice, flat):
        for n in range(5):
            await alice.post(
                f"/api/v1/groups/{flat['id']}/expenses",
                json=expense_payload(alice.id, [alice.id], description=f"Item {n}"),
            )
        first = data_of(await alice.get(f"/api/v1/groups/{flat['id']}/expenses?limit=2"))
        assert len(first["items"]) == 2
        assert first["next_cursor"] is not None

        second = data_of(
            await alice.get(
                f"/api/v1/groups/{flat['id']}/expenses?limit=2&cursor={first['next_cursor']}"
            )
        )
        assert len(second["items"]) == 2
        first_ids = {i["id"] for i in first["items"]}
        assert first_ids.isdisjoint({i["id"] for i in second["items"]})

    async def test_list_includes_names_and_my_share(self, alice, bob, flat):
        await alice.post(
            f"/api/v1/groups/{flat['id']}/expenses",
            json=expense_payload(alice.id, [alice.id, bob.id]),
        )
        listed = data_of(await bob.get(f"/api/v1/groups/{flat['id']}/expenses"))
        item = listed["items"][0]
        assert item["paid_by_name"] == alice.name
        assert item["my_share"] == "50.00"
