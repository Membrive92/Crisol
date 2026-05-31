"""Tests del submódulo WebAuthn / Passkeys.

`webauthn.verify_*` se mockea: testar la criptografía de WebAuthn requeriría
generar attestation/assertion reales con un authenticator simulado. Los
tests aquí cubren el resto: persistencia de challenges, lifecycle de
credenciales, aislamiento por usuario, manejo de errores y emisión de
tokens al autenticar.
"""

from __future__ import annotations

import base64
import json
from typing import Any
from unittest.mock import patch

from httpx import AsyncClient
from webauthn.helpers.exceptions import (
    InvalidAuthenticationResponse,
    InvalidRegistrationResponse,
)


async def _register_user(
    client: AsyncClient, email: str = "passkey@example.com"
) -> tuple[str, dict[str, Any]]:
    """Registra un usuario y devuelve (access_token, body)."""
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Pkey"},
    )
    body = r.json()
    return body["access_token"], body


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _client_data_json(challenge_b64: str) -> str:
    """Construye un `clientDataJSON` base64url con el challenge de las options.
    `verify_authentication_response` está mockeado en estos tests, así que sólo
    importa que el backend consuma el challenge correcto por valor."""
    raw = json.dumps(
        {
            "type": "webauthn.get",
            "challenge": challenge_b64,
            "origin": "http://localhost:3030",
        }
    ).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


class _FakeRegistration:
    def __init__(self, credential_id: bytes, public_key: bytes, sign_count: int = 0):
        self.credential_id = credential_id
        self.credential_public_key = public_key
        self.sign_count = sign_count


class _FakeAuthentication:
    def __init__(self, new_sign_count: int):
        self.new_sign_count = new_sign_count


# ─────────────────────────────────────
# Registration
# ─────────────────────────────────────


async def test_registration_options_requires_auth(client: AsyncClient) -> None:
    r = await client.post("/auth/webauthn/register-options")
    assert r.status_code == 401


async def test_registration_options_returns_challenge(client: AsyncClient) -> None:
    token, _ = await _register_user(client, "regopts@example.com")
    r = await client.post("/auth/webauthn/register-options", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert "options" in body
    options = body["options"]
    assert "challenge" in options
    assert options["rp"]["id"] == "localhost"
    assert options["user"]["name"] == "regopts@example.com"


async def test_register_verify_persists_credential(client: AsyncClient) -> None:
    token, _ = await _register_user(client, "regverify@example.com")

    # 1. Pedir options para que se guarde el challenge.
    await client.post("/auth/webauthn/register-options", headers=_auth(token))

    # 2. Mockear verify_registration_response y devolver una credencial fake.
    fake_cred_id = b"\x01\x02\x03\x04" * 4
    fake_pub = b"\xaa" * 64
    fake_credential = {
        "id": "fake-id",
        "rawId": "fake-id",
        "type": "public-key",
        "response": {"transports": ["internal", "hybrid"]},
    }
    with patch(
        "app.modules.auth.webauthn.service.verify_registration_response",
        return_value=_FakeRegistration(fake_cred_id, fake_pub, sign_count=0),
    ):
        r = await client.post(
            "/auth/webauthn/register-verify",
            json={"credential": fake_credential, "label": "MacBook"},
            headers=_auth(token),
        )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["label"] == "MacBook"
    assert body["transports"] == "internal,hybrid"

    # Listar y comprobar que aparece.
    r_list = await client.get("/auth/webauthn", headers=_auth(token))
    assert r_list.status_code == 200
    items = r_list.json()
    assert len(items) == 1
    assert items[0]["label"] == "MacBook"


async def test_register_verify_without_options_fails(client: AsyncClient) -> None:
    """Si no pediste options antes, no hay challenge para verificar."""
    token, _ = await _register_user(client, "noopts@example.com")
    fake_credential = {
        "id": "x",
        "rawId": "x",
        "type": "public-key",
        "response": {},
    }
    with patch(
        "app.modules.auth.webauthn.service.verify_registration_response",
        return_value=_FakeRegistration(b"\x00" * 16, b"\x00" * 32),
    ):
        r = await client.post(
            "/auth/webauthn/register-verify",
            json={"credential": fake_credential},
            headers=_auth(token),
        )
    assert r.status_code == 400
    assert "challenge" in r.json()["detail"].lower()


async def test_register_verify_invalid_attestation(client: AsyncClient) -> None:
    """Si la lib rechaza la attestation, devolvemos 400 con mensaje claro."""
    token, _ = await _register_user(client, "badatt@example.com")
    await client.post("/auth/webauthn/register-options", headers=_auth(token))

    with patch(
        "app.modules.auth.webauthn.service.verify_registration_response",
        side_effect=InvalidRegistrationResponse("bad signature"),
    ):
        r = await client.post(
            "/auth/webauthn/register-verify",
            json={"credential": {"id": "x", "rawId": "x", "type": "public-key", "response": {}}},
            headers=_auth(token),
        )
    assert r.status_code == 400
    assert "inválido" in r.json()["detail"].lower()


# ─────────────────────────────────────
# Authentication
# ─────────────────────────────────────


async def test_auth_options_unknown_user_returns_400(client: AsyncClient) -> None:
    r = await client.post(
        "/auth/webauthn/authenticate-options",
        json={"email": "ghost@example.com"},
    )
    assert r.status_code == 400


async def test_auth_options_user_without_passkeys_returns_400(client: AsyncClient) -> None:
    await _register_user(client, "nopkey@example.com")
    r = await client.post(
        "/auth/webauthn/authenticate-options",
        json={"email": "nopkey@example.com"},
    )
    assert r.status_code == 400


async def test_full_passkey_authentication_flow_issues_tokens(
    client: AsyncClient,
) -> None:
    """Flujo completo: registro de passkey → authenticate-options → verify → tokens."""
    token, _ = await _register_user(client, "fullflow@example.com")

    # Registramos passkey (paso ya cubierto en otro test, lo replicamos).
    await client.post("/auth/webauthn/register-options", headers=_auth(token))
    fake_cred_id = b"\x99" * 16
    fake_pub = b"\xbb" * 64
    with patch(
        "app.modules.auth.webauthn.service.verify_registration_response",
        return_value=_FakeRegistration(fake_cred_id, fake_pub, sign_count=0),
    ):
        await client.post(
            "/auth/webauthn/register-verify",
            json={
                "credential": {
                    "id": "x",
                    "rawId": "x",
                    "type": "public-key",
                    "response": {"transports": ["internal"]},
                },
                "label": "Demo",
            },
            headers=_auth(token),
        )

    # Cliente "fresco" (sin auth) — pide options para autenticarse por passkey.
    client.cookies.clear()
    r_opts = await client.post(
        "/auth/webauthn/authenticate-options",
        json={"email": "fullflow@example.com"},
    )
    assert r_opts.status_code == 200

    # Verify: enviamos el rawId base64url del credential_id que conoce el back.
    import base64

    raw_id = base64.urlsafe_b64encode(fake_cred_id).rstrip(b"=").decode("ascii")
    fake_assertion = {
        "id": raw_id,
        "rawId": raw_id,
        "type": "public-key",
        "response": {"clientDataJSON": _client_data_json(r_opts.json()["options"]["challenge"])},
    }
    with patch(
        "app.modules.auth.webauthn.service.verify_authentication_response",
        return_value=_FakeAuthentication(new_sign_count=1),
    ):
        r_verify = await client.post(
            "/auth/webauthn/authenticate-verify",
            json={"email": "fullflow@example.com", "credential": fake_assertion},
        )
    assert r_verify.status_code == 200, r_verify.text
    body = r_verify.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert "set-cookie" in {k.lower() for k in r_verify.headers}


async def test_authenticate_invalid_assertion_returns_401(client: AsyncClient) -> None:
    token, _ = await _register_user(client, "badasrt@example.com")
    await client.post("/auth/webauthn/register-options", headers=_auth(token))
    fake_cred_id = b"\x33" * 16
    with patch(
        "app.modules.auth.webauthn.service.verify_registration_response",
        return_value=_FakeRegistration(fake_cred_id, b"\xcc" * 64),
    ):
        await client.post(
            "/auth/webauthn/register-verify",
            json={
                "credential": {
                    "id": "x",
                    "rawId": "x",
                    "type": "public-key",
                    "response": {},
                },
            },
            headers=_auth(token),
        )

    client.cookies.clear()
    await client.post(
        "/auth/webauthn/authenticate-options",
        json={"email": "badasrt@example.com"},
    )

    import base64

    raw_id = base64.urlsafe_b64encode(fake_cred_id).rstrip(b"=").decode("ascii")
    with patch(
        "app.modules.auth.webauthn.service.verify_authentication_response",
        side_effect=InvalidAuthenticationResponse("bad sig"),
    ):
        r = await client.post(
            "/auth/webauthn/authenticate-verify",
            json={
                "email": "badasrt@example.com",
                "credential": {
                    "id": raw_id,
                    "rawId": raw_id,
                    "type": "public-key",
                    "response": {},
                },
            },
        )
    assert r.status_code == 401


# ─────────────────────────────────────
# Listing / deletion / isolation
# ─────────────────────────────────────


async def test_list_passkeys_empty(client: AsyncClient) -> None:
    token, _ = await _register_user(client, "empty@example.com")
    r = await client.get("/auth/webauthn", headers=_auth(token))
    assert r.status_code == 200
    assert r.json() == []


async def test_delete_passkey(client: AsyncClient) -> None:
    token, _ = await _register_user(client, "del@example.com")
    await client.post("/auth/webauthn/register-options", headers=_auth(token))
    with patch(
        "app.modules.auth.webauthn.service.verify_registration_response",
        return_value=_FakeRegistration(b"\x44" * 16, b"\xdd" * 64),
    ):
        created = await client.post(
            "/auth/webauthn/register-verify",
            json={
                "credential": {
                    "id": "x",
                    "rawId": "x",
                    "type": "public-key",
                    "response": {},
                }
            },
            headers=_auth(token),
        )
    pkid = created.json()["id"]

    r_del = await client.delete(f"/auth/webauthn/{pkid}", headers=_auth(token))
    assert r_del.status_code == 204

    r_list = await client.get("/auth/webauthn", headers=_auth(token))
    assert r_list.json() == []


async def test_relabel_passkey(client: AsyncClient) -> None:
    token, _ = await _register_user(client, "relabel@example.com")
    await client.post("/auth/webauthn/register-options", headers=_auth(token))
    with patch(
        "app.modules.auth.webauthn.service.verify_registration_response",
        return_value=_FakeRegistration(b"\x77" * 16, b"\xff" * 64),
    ):
        created = await client.post(
            "/auth/webauthn/register-verify",
            json={
                "credential": {
                    "id": "x",
                    "rawId": "x",
                    "type": "public-key",
                    "response": {},
                },
                "label": "Old name",
            },
            headers=_auth(token),
        )
    pkid = created.json()["id"]

    r = await client.patch(
        f"/auth/webauthn/{pkid}",
        json={"label": "MacBook personal"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["label"] == "MacBook personal"


async def test_relabel_other_user_passkey_returns_404(client: AsyncClient) -> None:
    """A no puede renombrar passkeys de B (404 para no filtrar existencia)."""
    token_a, _ = await _register_user(client, "rl-a@example.com")
    token_b, _ = await _register_user(client, "rl-b@example.com")
    await client.post("/auth/webauthn/register-options", headers=_auth(token_a))
    with patch(
        "app.modules.auth.webauthn.service.verify_registration_response",
        return_value=_FakeRegistration(b"\x88" * 16, b"\xff" * 64),
    ):
        created = await client.post(
            "/auth/webauthn/register-verify",
            json={
                "credential": {
                    "id": "x",
                    "rawId": "x",
                    "type": "public-key",
                    "response": {},
                }
            },
            headers=_auth(token_a),
        )
    pkid = created.json()["id"]
    r = await client.patch(
        f"/auth/webauthn/{pkid}",
        json={"label": "Hijacked"},
        headers=_auth(token_b),
    )
    assert r.status_code == 404


async def test_conditional_ui_options_no_email(client: AsyncClient) -> None:
    """authenticate-options sin email devuelve options sin allowCredentials."""
    r = await client.post("/auth/webauthn/authenticate-options", json={})
    assert r.status_code == 200
    options = r.json()["options"]
    assert "challenge" in options
    assert not options.get("allowCredentials")


async def test_conditional_ui_full_flow(client: AsyncClient) -> None:
    """El usuario se autentica sin email — el credential_id lo identifica."""
    token, _ = await _register_user(client, "condui@example.com")
    await client.post("/auth/webauthn/register-options", headers=_auth(token))
    fake_cred_id = b"\xaa" * 16
    with patch(
        "app.modules.auth.webauthn.service.verify_registration_response",
        return_value=_FakeRegistration(fake_cred_id, b"\xbb" * 64),
    ):
        await client.post(
            "/auth/webauthn/register-verify",
            json={
                "credential": {
                    "id": "x",
                    "rawId": "x",
                    "type": "public-key",
                    "response": {},
                }
            },
            headers=_auth(token),
        )

    client.cookies.clear()
    r_opts = await client.post("/auth/webauthn/authenticate-options", json={})

    import base64

    raw_id = base64.urlsafe_b64encode(fake_cred_id).rstrip(b"=").decode("ascii")
    with patch(
        "app.modules.auth.webauthn.service.verify_authentication_response",
        return_value=_FakeAuthentication(new_sign_count=1),
    ):
        r = await client.post(
            "/auth/webauthn/authenticate-verify",
            json={
                "credential": {
                    "id": raw_id,
                    "rawId": raw_id,
                    "type": "public-key",
                    "response": {
                        "clientDataJSON": _client_data_json(r_opts.json()["options"]["challenge"])
                    },
                }
            },
        )
    assert r.status_code == 200, r.text
    assert "access_token" in r.json()


async def test_user_isolation_in_list(client: AsyncClient) -> None:
    """Las passkeys de A no aparecen al listar como B."""
    token_a, _ = await _register_user(client, "iso-a@example.com")
    token_b, _ = await _register_user(client, "iso-b@example.com")

    await client.post("/auth/webauthn/register-options", headers=_auth(token_a))
    with patch(
        "app.modules.auth.webauthn.service.verify_registration_response",
        return_value=_FakeRegistration(b"\x55" * 16, b"\xee" * 64),
    ):
        await client.post(
            "/auth/webauthn/register-verify",
            json={
                "credential": {
                    "id": "x",
                    "rawId": "x",
                    "type": "public-key",
                    "response": {},
                }
            },
            headers=_auth(token_a),
        )

    r_a = await client.get("/auth/webauthn", headers=_auth(token_a))
    r_b = await client.get("/auth/webauthn", headers=_auth(token_b))
    assert len(r_a.json()) == 1
    assert r_b.json() == []
