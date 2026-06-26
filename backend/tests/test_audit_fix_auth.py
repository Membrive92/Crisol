"""Tests del AUDIT-FIX de auth (remediación conservadora).

Cubre los hallazgos testeables sin levantar el servidor real (se usa el
`client` ASGITransport del conftest, igual que `test_auth.py`):

- rate-limit-client-host-tras-proxy → `get_client_key` / `_real_client_ip`.
- logout-exige-access-token-valido  → logout sin access token válido.
- refresh-rotacion-sin-vida-absoluta-de-sesion → límite absoluto de sesión.
- regresiones del happy-path de refresh / logout.

NO se cubre aquí el flujo WebAuthn (register-verify por valor) porque exige
una attestation firmada por un authenticator real; ese cambio se valida con
los tests de webauthn existentes + prueba manual.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.rate_limit import _real_client_ip, get_client_key

# ─────────────────────────────────────────────────────────────────────────────
# Finding 1 — rate-limit detrás de proxy: IP real respetando el primer hop
# ─────────────────────────────────────────────────────────────────────────────


class _FakeClient:
    def __init__(self, host: str) -> None:
        self.host = host


class _FakeURL:
    def __init__(self, path: str) -> None:
        self.path = path


class _FakeRequest:
    """Stub mínimo de `starlette.Request` para `_real_client_ip`/`get_client_key`."""

    def __init__(self, *, client_host: str, headers: dict[str, str], path: str = "/auth/login"):
        self.client = _FakeClient(client_host)
        # Las cabeceras en Starlette son case-insensitive; el código las lee en
        # minúsculas, así que normalizamos aquí.
        self.headers = {k.lower(): v for k, v in headers.items()}
        self.url = _FakeURL(path)


def test_real_ip_ignores_forwarded_from_untrusted_peer() -> None:
    """Un cliente directo (no-proxy) NO puede falsear su IP vía XFF."""
    req = _FakeRequest(
        client_host="203.0.113.9",  # no está en trusted proxies
        headers={"X-Forwarded-For": "1.2.3.4"},
    )
    assert _real_client_ip(req) == "203.0.113.9"  # type: ignore[arg-type]


def test_real_ip_trusts_forwarded_from_loopback_proxy() -> None:
    """Tras el proxy de confianza (loopback default), la IP real sale de XFF."""
    req = _FakeRequest(
        client_host="127.0.0.1",
        headers={"X-Forwarded-For": "198.51.100.7, 127.0.0.1"},
    )
    assert _real_client_ip(req) == "198.51.100.7"  # type: ignore[arg-type]


def test_real_ip_falls_back_to_x_real_ip() -> None:
    """Sin XFF pero con X-Real-IP desde un proxy de confianza → X-Real-IP."""
    req = _FakeRequest(
        client_host="::1",
        headers={"X-Real-IP": "198.51.100.42"},
    )
    assert _real_client_ip(req) == "198.51.100.42"  # type: ignore[arg-type]


def test_real_ip_proxy_without_forward_headers_uses_peer() -> None:
    """Proxy de confianza sin cabeceras → cae a la IP de la conexión."""
    req = _FakeRequest(client_host="127.0.0.1", headers={})
    assert _real_client_ip(req) == "127.0.0.1"  # type: ignore[arg-type]


def test_client_key_includes_real_ip_and_path() -> None:
    req = _FakeRequest(
        client_host="127.0.0.1",
        headers={"X-Forwarded-For": "198.51.100.7"},
        path="/auth/login",
    )
    assert get_client_key(req) == "198.51.100.7:/auth/login"  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers HTTP (espejo de test_auth.py)
# ─────────────────────────────────────────────────────────────────────────────


async def _register(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Audit User"},
    )
    assert response.status_code == 201
    return response.json()


# ─────────────────────────────────────────────────────────────────────────────
# Finding 4 — logout NO debe exigir un access token válido
# ─────────────────────────────────────────────────────────────────────────────


async def test_logout_without_access_token_succeeds(client: AsyncClient) -> None:
    """Con el access caducado/ausente el usuario igual puede cerrar sesión:
    la autorización la da el secreto del refresh, no el access."""
    body = await _register(client, email="logout_noaccess@example.com")
    refresh_token = body["refresh_token"]

    # SIN cabecera Authorization → antes daba 401, ahora 204.
    client.cookies.clear()
    resp = await client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert resp.status_code == 204

    # El refresh quedó revocado.
    client.cookies.clear()
    after = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert after.status_code == 401


async def test_logout_still_rejects_forged_secret(client: AsyncClient) -> None:
    """Regresión: sin access token, un refresh con token_id válido pero secreto
    basura NO revoca la sesión legítima (la autorización exige el secreto)."""
    body = await _register(client, email="logout_forged2@example.com")
    refresh_token = body["refresh_token"]
    token_id = refresh_token.split(".")[0]
    forged = f"{token_id}.not-the-real-secret"

    client.cookies.clear()
    forged_resp = await client.post("/auth/logout", json={"refresh_token": forged})
    assert forged_resp.status_code == 401

    # El token legítimo sigue vivo.
    client.cookies.clear()
    ok = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert ok.status_code == 200


async def test_logout_without_token_anywhere_401(client: AsyncClient) -> None:
    """Sin cookie ni body → 401 (no se puede revocar nada sin presentar token)."""
    client.cookies.clear()
    resp = await client.post("/auth/logout", json={})
    assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# Finding 2 — vida absoluta de la sesión
# ─────────────────────────────────────────────────────────────────────────────


async def _backdate_family(test_engine, email: str, days_ago: int) -> None:  # type: ignore[no-untyped-def]
    """Retrasa `created_at` de TODOS los refresh tokens del usuario `email`."""
    new_created = datetime.now(UTC) - timedelta(days=days_ago)
    async with test_engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE refresh_tokens SET created_at = :created "
                "WHERE user_id = (SELECT id FROM users WHERE email = :email)"
            ),
            {"created": new_created, "email": email},
        )


async def test_refresh_blocked_after_absolute_session_lifetime(
    client: AsyncClient, test_engine  # type: ignore[no-untyped-def]
) -> None:
    """Una familia más antigua que la vida absoluta (90 días default) ya no
    puede refrescar: el usuario debe re-loguearse."""
    email = "ancient_session@example.com"
    body = await _register(client, email=email)
    refresh_token = body["refresh_token"]

    # Envejecemos la familia 200 días → supera el cap absoluto (90 por default).
    await _backdate_family(test_engine, email, days_ago=200)

    client.cookies.clear()
    resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 401
    assert "antig" in resp.json()["detail"].lower()


async def test_refresh_within_absolute_lifetime_ok(
    client: AsyncClient, test_engine  # type: ignore[no-untyped-def]
) -> None:
    """Una familia joven (1 día) refresca con normalidad: el cap no molesta."""
    email = "young_session@example.com"
    body = await _register(client, email=email)
    refresh_token = body["refresh_token"]

    await _backdate_family(test_engine, email, days_ago=1)

    client.cookies.clear()
    resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert resp.json()["refresh_token"] != refresh_token


# ─────────────────────────────────────────────────────────────────────────────
# Finding 3 — refresh de token expirado: 401 limpio (sin revoke que se revierte)
# ─────────────────────────────────────────────────────────────────────────────


async def test_refresh_expired_token_returns_401(
    client: AsyncClient, test_engine  # type: ignore[no-untyped-def]
) -> None:
    """Un refresh expirado → 401. (La rama ya no intenta un revoke inútil que
    el router nunca commitea.)"""
    email = "expired_refresh@example.com"
    body = await _register(client, email=email)
    refresh_token = body["refresh_token"]

    # Expiramos el token in-place.
    past = datetime.now(UTC) - timedelta(days=1)
    async with test_engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE refresh_tokens SET expires_at = :past "
                "WHERE user_id = (SELECT id FROM users WHERE email = :email)"
            ),
            {"past": past, "email": email},
        )

    client.cookies.clear()
    resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 401
    assert "expirado" in resp.json()["detail"].lower()


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
