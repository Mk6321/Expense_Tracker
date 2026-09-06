from __future__ import annotations

import os
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Point at a real Postgres with TEST_DATABASE_URL to exercise NUMERIC/JSONB for real;
# the default keeps the suite runnable offline and still exact (see money_type.py).
TEST_DB_URL = os.getenv("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("DATABASE_URL", TEST_DB_URL)
os.environ.setdefault("JWT_SECRET", "test-secret-not-used-anywhere-real")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("COOKIE_SAMESITE", "lax")

from app.core.db import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.repositories import category_repo  # noqa: E402


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(TEST_DB_URL, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False, autoflush=False)


@pytest_asyncio.fixture
async def client(session_factory):
    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    async with session_factory() as session:
        await category_repo.ensure_defaults(session)
        await session.commit()

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


class Actor:
    """A registered user plus the auth header their requests need."""

    def __init__(self, client: AsyncClient, user: dict, token: str):
        self.client = client
        self.id: int = user["id"]
        self.name: str = user["name"]
        self.email: str = user["email"]
        self.token = token

    @property
    def auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def post(self, url: str, json=None, **kw):
        headers = {**self.auth, **kw.pop("headers", {})}
        return await self.client.post(url, json=json, headers=headers, **kw)

    async def get(self, url: str, **kw):
        return await self.client.get(url, headers=self.auth, **kw)

    async def put(self, url: str, json=None, **kw):
        return await self.client.put(url, json=json, headers=self.auth, **kw)

    async def delete(self, url: str, **kw):
        return await self.client.delete(url, headers=self.auth, **kw)


@pytest_asyncio.fixture
async def make_user(client):
    async def _make(name: str, email: str | None = None) -> Actor:
        email = email or f"{name.lower().replace(' ', '.')}@example.com"
        response = await client.post(
            "/api/v1/auth/register",
            json={"name": name, "email": email, "password": "correct-horse-battery"},
        )
        assert response.status_code == 201, response.text
        data = response.json()["data"]
        return Actor(client, data["user"], data["access_token"])

    return _make


@pytest_asyncio.fixture
async def alice(make_user) -> Actor:
    return await make_user("Alice")


@pytest_asyncio.fixture
async def bob(make_user) -> Actor:
    return await make_user("Bob")


@pytest_asyncio.fixture
async def group(alice: Actor):
    response = await alice.post("/api/v1/groups", json={"name": "Flat 3B", "currency": "INR"})
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def join(owner: Actor, group_id: int, member: Actor) -> None:
    invite = await owner.post(f"/api/v1/groups/{group_id}/invites")
    code = invite.json()["data"]["code"]
    response = await member.post("/api/v1/groups/join", json={"invite_code": code})
    assert response.status_code == 200, response.text


def money(value: str) -> Decimal:
    return Decimal(value)


def data_of(response):
    assert response.status_code < 400, response.text
    return response.json()["data"]
