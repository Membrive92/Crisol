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
    """Flujo mobile (body-only): un refresh ya rotado no se puede reutilizar."""
    _, body = await _register(client, email="revoked@example.com")
    old_refresh = body["refresh_token"]

    # Simulamos cliente sin cookies (mobile usa expo-secure-store + body).
    client.cookies.clear()
    response1 = await client.post(
        "/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert response1.status_code == 200

    # El backend setea cookie en response1; httpx la guarda. Limpiamos otra
    # vez para que la segunda petición sí mande el body antiguo y nada más.
    client.cookies.clear()
    response2 = await client.post(
        "/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert response2.status_code == 401


async def test_refresh_via_cookie(client: AsyncClient) -> None:
    """Flujo web: el refresh viaja en la cookie httpOnly, body vacío."""
    _, body = await _register(client, email="cookie@example.com")
    old_refresh = body["refresh_token"]

    response = await client.post("/auth/refresh", json={})
    assert response.status_code == 200
    new_body = response.json()
    assert new_body["refresh_token"] != old_refresh
    # La cookie nueva está en el response.
    set_cookie = response.headers.get("set-cookie", "")
    assert "finanzas_refresh=" in set_cookie
    assert "HttpOnly" in set_cookie


async def test_refresh_cookie_takes_precedence_over_body(client: AsyncClient) -> None:
    """Si llegan cookie + body distintos, gana la cookie (caso edge: web con body residual)."""
    _, body = await _register(client, email="precedence@example.com")
    cookie_refresh = body["refresh_token"]

    # Body con un valor inválido; la cookie sigue siendo válida → 200.
    response = await client.post(
        "/auth/refresh",
        json={"refresh_token": "definitely-not-a-real-token"},
    )
    assert response.status_code == 200
    assert response.json()["refresh_token"] != cookie_refresh


async def test_refresh_without_token_anywhere_401(client: AsyncClient) -> None:
    """Sin cookie ni body → 401 con mensaje claro."""
    response = await client.post("/auth/refresh", json={})
    assert response.status_code == 401
    assert "ausente" in response.json()["detail"].lower()


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
    # logout debe limpiar la cookie.
    set_cookie = response.headers.get("set-cookie", "")
    assert "finanzas_refresh=" in set_cookie

    # Refresh with the revoked token should fail. Limpiamos cookie por si
    # httpx mantuvo la versión obsoleta.
    client.cookies.clear()
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
