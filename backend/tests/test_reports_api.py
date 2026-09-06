from __future__ import annotations

import pytest_asyncio
from sqlalchemy import select

from app.models import AuditLog
from tests.conftest import data_of, join


@pytest_asyncio.fixture
async def spent(alice, bob, group):
    await join(alice, group["id"], bob)
    categories = data_of(await alice.get(f"/api/v1/groups/{group['id']}/categories"))
    food = next(c for c in categories if c["name"] == "Food & Drink")
    rent = next(c for c in categories if c["name"] == "Rent")

    for description, amount, on, category in [
        ("Pizza", "100.00", "2026-01-10", food),
        ("Sushi", "50.00", "2026-01-20", food),
        ("January rent", "1000.00", "2026-01-01", rent),
        ("February rent", "1000.00", "2026-02-01", rent),
    ]:
        await alice.post(
            f"/api/v1/groups/{group['id']}/expenses",
            json={
                "description": description,
                "amount": amount,
                "expense_date": on,
                "split_type": "equal",
                "category_id": category["id"],
                "paid_by": alice.id,
                "participants": [{"user_id": alice.id}, {"user_id": bob.id}],
            },
        )
    return group


class TestCategories:
    async def test_defaults_are_available_to_every_group(self, alice, group):
        categories = data_of(await alice.get(f"/api/v1/groups/{group['id']}/categories"))
        names = {c["name"] for c in categories}
        assert {"Food & Drink", "Rent", "Transport"} <= names
        assert all(c["group_id"] is None for c in categories)

    async def test_admin_can_add_a_group_category(self, alice, group):
        created = data_of(
            await alice.post(
                f"/api/v1/groups/{group['id']}/categories",
                json={"name": "Chai fund", "icon": "coffee"},
            )
        )
        assert created["group_id"] == group["id"]
        listed = data_of(await alice.get(f"/api/v1/groups/{group['id']}/categories"))
        assert "Chai fund" in {c["name"] for c in listed}

    async def test_member_cannot_add_a_category(self, alice, bob, group):
        await join(alice, group["id"], bob)
        response = await bob.post(
            f"/api/v1/groups/{group['id']}/categories", json={"name": "Nope"}
        )
        assert response.status_code == 403

    async def test_another_groups_category_cannot_be_used(self, alice, bob, group):
        other = data_of(await bob.post("/api/v1/groups", json={"name": "Other", "currency": "INR"}))
        sneaky = data_of(
            await bob.post(f"/api/v1/groups/{other['id']}/categories", json={"name": "Theirs"})
        )
        response = await alice.post(
            f"/api/v1/groups/{group['id']}/expenses",
            json={
                "description": "Test",
                "amount": "10.00",
                "expense_date": "2026-01-01",
                "split_type": "equal",
                "category_id": sneaky["id"],
                "paid_by": alice.id,
                "participants": [{"user_id": alice.id}],
            },
        )
        assert response.status_code == 422
        assert response.json()["error_code"] == "CATEGORY_NOT_FOUND"


class TestReports:
    async def test_summary(self, alice, spent):
        summary = data_of(await alice.get(f"/api/v1/groups/{spent['id']}/reports/summary"))
        assert summary["total_spend"] == "2150.00"
        assert summary["expense_count"] == 4
        assert summary["member_count"] == 2
        assert summary["my_total_paid"] == "2150.00"
        assert summary["my_total_share"] == "1075.00"
        assert summary["my_balance"] == "1075.00"
        assert summary["largest_expense"] == "1000.00"
        assert summary["average_expense"] == "537.50"
        assert summary["first_expense_date"] == "2026-01-01"
        assert summary["last_expense_date"] == "2026-02-01"

    async def test_by_category(self, alice, spent):
        rows = data_of(await alice.get(f"/api/v1/groups/{spent['id']}/reports/categories"))
        by_name = {r["category_name"]: r for r in rows}
        assert by_name["Rent"]["total"] == "2000.00"
        assert by_name["Food & Drink"]["total"] == "150.00"
        assert by_name["Food & Drink"]["expense_count"] == 2
        # Sorted biggest first, and the percentages account for everything.
        assert rows[0]["category_name"] == "Rent"
        assert sum(float(r["percentage"]) for r in rows) == 100.0

    async def test_by_member(self, alice, bob, spent):
        rows = data_of(await alice.get(f"/api/v1/groups/{spent['id']}/reports/members"))
        by_user = {r["user_id"]: r for r in rows}
        assert by_user[alice.id]["total_paid"] == "2150.00"
        assert by_user[alice.id]["expense_count"] == 4
        assert by_user[bob.id]["total_paid"] == "0.00"
        assert by_user[bob.id]["balance"] == "-1075.00"

    async def test_monthly(self, alice, spent):
        rows = data_of(await alice.get(f"/api/v1/groups/{spent['id']}/reports/monthly"))
        assert [r["month"] for r in rows] == ["2026-01", "2026-02"]
        assert rows[0]["total"] == "1150.00"
        assert rows[0]["expense_count"] == 3
        assert rows[0]["my_share"] == "575.00"

    async def test_reports_exclude_reversed_expenses(self, alice, spent):
        listed = data_of(await alice.get(f"/api/v1/groups/{spent['id']}/expenses"))
        rent = next(i for i in listed["items"] if i["description"] == "February rent")
        await alice.delete(f"/api/v1/expenses/{rent['id']}")

        summary = data_of(await alice.get(f"/api/v1/groups/{spent['id']}/reports/summary"))
        assert summary["total_spend"] == "1150.00"
        assert summary["expense_count"] == 3


class TestAuditLog:
    """Section 10 -- every financial mutation leaves a trail."""

    async def _entries(self, session_factory, group_id: int):
        async with session_factory() as session:
            result = await session.execute(
                select(AuditLog).where(AuditLog.group_id == group_id).order_by(AuditLog.id)
            )
            return list(result.scalars())

    async def test_expense_lifecycle_is_logged(self, alice, bob, group, session_factory):
        await join(alice, group["id"], bob)
        created = data_of(
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
        )
        await alice.put(
            f"/api/v1/expenses/{created['id']}",
            json={
                "description": "Pizza night",
                "amount": "120.00",
                "expense_date": "2026-01-01",
                "split_type": "equal",
                "paid_by": alice.id,
                "version": created["version"],
                "participants": [{"user_id": alice.id}, {"user_id": bob.id}],
            },
        )
        await alice.delete(f"/api/v1/expenses/{created['id']}")

        entries = await self._entries(session_factory, group["id"])
        expense_actions = [e.action for e in entries if e.entity_type == "expense"]
        assert expense_actions == ["create", "update", "reverse"]

        update_entry = next(e for e in entries if e.action == "update")
        assert update_entry.old_value["amount"] == "100.00"
        assert update_entry.new_value["amount"] == "120.00"
        assert update_entry.user_id == alice.id

    async def test_membership_and_settlement_changes_are_logged(
        self, alice, bob, group, session_factory
    ):
        await join(alice, group["id"], bob)
        await alice.put(
            f"/api/v1/groups/{group['id']}/members/{bob.id}/role", json={"role": "viewer"}
        )
        await alice.post(
            f"/api/v1/groups/{group['id']}/settlements",
            json={
                "from_user_id": bob.id,
                "to_user_id": alice.id,
                "amount": "10.00",
                "settlement_date": "2026-01-01",
            },
        )
        entries = await self._entries(session_factory, group["id"])
        actions = {(e.entity_type, e.action) for e in entries}
        assert ("group", "create") in actions
        assert ("group_member", "member_add") in actions
        assert ("group_member", "role_change") in actions
        assert ("settlement", "create") in actions
