from __future__ import annotations

from tests.conftest import data_of


async def test_register_returns_token_and_sets_refresh_cookie(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={"name": "Nina", "email": "nina@example.com", "password": "correct-horse-battery"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["user"]["email"] == "nina@example.com"
    assert body["data"]["access_token"]
    # The refresh token is httpOnly-cookie only -- it must never be in the body.
    assert "refresh_token" not in body["data"]
    assert "et_refresh" in response.cookies


async def test_password_is_never_returned(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={"name": "Nina", "email": "nina@example.com", "password": "correct-horse-battery"},
    )
    assert "password" not in response.text
    assert "hash" not in response.text.lower()


async def test_duplicate_email_is_rejected(client, alice):
    response = await client.post(
        "/api/v1/auth/register",
        json={"name": "Other", "email": alice.email, "password": "correct-horse-battery"},
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "EMAIL_TAKEN"


async def test_short_password_is_rejected(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={"name": "Nina", "email": "nina@example.com", "password": "short"},
    )
    assert response.status_code == 422
    assert response.json()["success"] is False


async def test_login_succeeds_and_wrong_password_fails(client, alice):
    ok = await client.post(
        "/api/v1/auth/login",
        json={"email": alice.email, "password": "correct-horse-battery"},
    )
    assert ok.status_code == 200

    bad = await client.post(
        "/api/v1/auth/login", json={"email": alice.email, "password": "wrong-password"}
    )
    assert bad.status_code == 401
    assert bad.json()["error_code"] == "INVALID_CREDENTIALS"


async def test_unknown_email_gives_the_same_error_as_a_wrong_password(client, alice):
    """Otherwise the login form doubles as a way to enumerate registered emails."""
    unknown = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever-here"}
    )
    wrong = await client.post(
        "/api/v1/auth/login", json={"email": alice.email, "password": "whatever-here"}
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["error_code"] == wrong.json()["error_code"]
    assert unknown.json()["message"] == wrong.json()["message"]


async def test_me_requires_a_token(client, alice):
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    assert (
        await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer nonsense"})
    ).status_code == 401
    assert data_of(await alice.get("/api/v1/auth/me"))["email"] == alice.email


async def test_refresh_rotates_the_cookie(client, alice):
    await client.post(
        "/api/v1/auth/login",
        json={"email": alice.email, "password": "correct-horse-battery"},
    )
    first = client.cookies.get("et_refresh")

    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 200
    assert response.json()["data"]["access_token"]
    assert client.cookies.get("et_refresh") != first


async def test_refresh_without_a_cookie_fails(client):
    client.cookies.clear()
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401
    assert response.json()["error_code"] == "REFRESH_MISSING"


async def test_an_access_token_cannot_be_used_as_a_refresh_token(client, alice):
    client.cookies.set("et_refresh", alice.token)
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401
    assert response.json()["error_code"] == "TOKEN_INVALID"
