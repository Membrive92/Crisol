"""Tests del módulo auth — registro, login, refresh, logout, me, aislamiento."""

from __future__ import annotations

from httpx import AsyncClient


async def _register(client: AsyncClient, email: str = "test@example.com") -> dict[str, object]:
    """Helper: registra un usuario y devuelve el body con tokens."""
    response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "SecurePass123",
            "display_name": "Test User",
        },
    )
    return response.status_code, response.json()


async def _login(client: AsyncClient, email: str = "test@example.com") -> dict[str, object]:
    """Helper: login y devuelve el body con tokens."""
    response = await client.post(
        "/auth/login",
        json={"email": email, "password": "SecurePass123"},
    )
    return response.status_code, response.json()


# ─────────────────────────────────────
# Registro
# ─────────────────────────────────────


async def test_register_ok(client: AsyncClient) -> None:
    status_code, body = await _register(client)
    assert status_code == 201
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


async def test_register_duplicate_email(client: AsyncClient) -> None:
    status_code, _ = await _register(client, email="dup@example.com")
    assert status_code == 201

    status_code2, body2 = await _register(client, email="dup@example.com")
    assert status_code2 == 409
    assert "ya está registrado" in body2["detail"]


# ─────────────────────────────────────
# Login
# ─────────────────────────────────────


async def test_login_ok(client: AsyncClient) -> None:
    await _register(client, email="login@example.com")

    status_code, body = await _login(client, email="login@example.com")
    assert status_code == 200
    assert "access_token" in body
    assert "refresh_token" in body


async def test_login_wrong_password(client: AsyncClient) -> None:
    await _register(client, email="wrongpw@example.com")

    response = await client.post(
        "/auth/login",
        json={"email": "wrongpw@example.com", "password": "WrongPassword999"},
    )
    assert response.status_code == 401


async def test_login_nonexistent_user(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "SomePassword123"},
    )
    assert response.status_code == 401


# ─────────────────────────────────────
# Refresh
# ─────────────────────────────────────


async def test_refresh_ok(client: AsyncClient) -> None:
    _, body = await _register(client, email="refresh@example.com")
    old_refresh = body["refresh_token"]

    response = await client.post(
        "/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert response.status_code == 200
    new_body = response.json()
    assert "access_token" in new_body
    assert new_body["refresh_token"] != old_refresh


async def test_refresh_revoked_token(client: AsyncClient) -> None:
    _, body = await _register(client, email="revoked@example.com")
    old_refresh = body["refresh_token"]

    # First refresh — should succeed and revoke the old token
    response1 = await client.post(
        "/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert response1.status_code == 200

    # Second refresh with the same (now revoked) token — should fail
    response2 = await client.post(
        "/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert response2.status_code == 401


# ─────────────────────────────────────
# Logout
# ─────────────────────────────────────


async def test_logout_ok(client: AsyncClient) -> None:
    _, body = await _register(client, email="logout@example.com")
    access = body["access_token"]
    refresh_token = body["refresh_token"]

    response = await client.post(
        "/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 204

    # Refresh with the revoked token should fail
    response2 = await client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response2.status_code == 401


# ─────────────────────────────────────
# Me
# ─────────────────────────────────────


async def test_me_ok(client: AsyncClient) -> None:
    _, body = await _register(client, email="me@example.com")
    access = body["access_token"]

    response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "me@example.com"
    assert data["display_name"] == "Test User"
    assert "password_hash" not in data


async def test_me_unauthorized(client: AsyncClient) -> None:
    response = await client.get("/auth/me")
    assert response.status_code == 401


# ─────────────────────────────────────
# Aislamiento multi-usuario
# ─────────────────────────────────────


async def test_user_isolation(client: AsyncClient) -> None:
    """El usuario A no puede acceder al /me del usuario B con su propio token."""
    _, body_a = await _register(client, email="userA@example.com")
    _, body_b = await _register(client, email="userB@example.com")

    me_a = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {body_a['access_token']}"},
    )
    me_b = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {body_b['access_token']}"},
    )

    assert me_a.json()["email"] == "userA@example.com"
    assert me_b.json()["email"] == "userB@example.com"
    assert me_a.json()["id"] != me_b.json()["id"]
