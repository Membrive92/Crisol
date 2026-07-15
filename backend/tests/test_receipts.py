"""Tests del módulo receipts (router + service) con mocks de IA y MinIO."""

from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from app.modules.ai.exceptions import AiUnavailableError
from app.modules.ai.schemas import ReceiptExtraction, ReceiptLineItem


def _sample_extraction() -> ReceiptExtraction:
    return ReceiptExtraction(
        merchant="Mercadona",
        occurred_at=None,
        currency="EUR",
        total=Decimal("12.34"),
        tax=Decimal("1.23"),
        line_items=[
            ReceiptLineItem(
                description="Pan",
                quantity=Decimal("1"),
                unit_price=Decimal("1.00"),
                total=Decimal("1.00"),
            ),
        ],
        raw_text="ticket",
    )


@contextmanager
def _mock_storage_and_ai(
    *,
    extraction: ReceiptExtraction | None = None,
    extract_side_effect: Exception | None = None,
) -> Any:
    """Mockea `storage.put_receipt`, `storage.delete_receipt` y la extracción."""
    delete_mock = AsyncMock(return_value=None)

    extract_kwargs: dict[str, Any] = {}
    if extract_side_effect is not None:
        extract_kwargs["side_effect"] = extract_side_effect
    else:
        extract_kwargs["return_value"] = extraction or _sample_extraction()

    with (
        patch(
            "app.modules.personal_finance.receipts.service.storage.put_receipt",
            new_callable=AsyncMock,
            return_value="fakekey/img.jpg",
        ),
        patch("app.modules.personal_finance.receipts.service.storage.delete_receipt", delete_mock),
        patch(
            "app.modules.personal_finance.receipts.service.ai_service.extract_receipt",
            new_callable=AsyncMock,
            **extract_kwargs,
        ),
    ):
        yield delete_mock


async def _setup_user(client: AsyncClient, email: str = "rcpt@example.com") -> tuple[str, str]:
    """Registra un usuario y crea una cuenta, devuelve (token, account_id)."""
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Rcpt"},
    )
    token = str(r.json()["access_token"])
    acc = await client.post(
        "/accounts",
        json={"name": "Cuenta principal", "type": "bank", "currency": "EUR"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return token, acc.json()["id"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_category(
    client: AsyncClient, token: str, name: str, kind: str = "expense"
) -> str:
    r = await client.post(
        "/categories", json={"name": name, "kind": kind}, headers=_auth(token)
    )
    assert r.status_code in (200, 201), r.text
    return str(r.json()["id"])


async def _extract_receipt_id(client: AsyncClient, token: str) -> str:
    """Extrae un ticket de muestra (merchant='Mercadona') y devuelve su id."""
    files = {"file": ("ticket.jpg", b"fake", "image/jpeg")}
    with _mock_storage_and_ai():
        extract = await client.post("/receipts/extract", files=files, headers=_auth(token))
    return str(extract.json()["receipt"]["id"])


async def _confirm(
    client: AsyncClient,
    token: str,
    receipt_id: str,
    account_id: str,
    **extra: Any,
) -> Any:
    payload: dict[str, Any] = {
        "account_id": account_id,
        "amount": "12.34",
        "occurred_at": "2026-04-15T13:45:00Z",
        "currency": "EUR",
        **extra,
    }
    return await client.post(
        f"/receipts/{receipt_id}/confirm", json=payload, headers=_auth(token)
    )


async def _only_tx(client: AsyncClient, token: str) -> dict[str, Any]:
    txs = (await client.get("/transactions", headers=_auth(token))).json()["items"]
    assert len(txs) == 1
    return dict(txs[0])


async def test_extract_creates_pending_receipt(client: AsyncClient) -> None:
    token, _account_id = await _setup_user(client)
    files = {"file": ("ticket.jpg", b"fake-image", "image/jpeg")}
    with _mock_storage_and_ai():
        r = await client.post("/receipts/extract", files=files, headers=_auth(token))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["receipt"]["status"] == "pending"
    assert body["receipt"]["blob_key"] == "fakekey/img.jpg"
    assert body["extraction"]["merchant"] == "Mercadona"
    assert body["extraction"]["total"] == "12.34"


async def test_extract_rejects_unsupported_image_type(client: AsyncClient) -> None:
    token, _account_id = await _setup_user(client, "badimg@example.com")
    files = {"file": ("ticket.gif", b"\x00\x00", "image/gif")}
    with _mock_storage_and_ai():
        r = await client.post("/receipts/extract", files=files, headers=_auth(token))
    assert r.status_code == 400


async def test_extract_empty_payload_rejected(client: AsyncClient) -> None:
    token, _account_id = await _setup_user(client, "empty@example.com")
    files = {"file": ("ticket.jpg", b"", "image/jpeg")}
    with _mock_storage_and_ai():
        r = await client.post("/receipts/extract", files=files, headers=_auth(token))
    assert r.status_code == 400


async def test_extract_ai_unavailable_cleans_blob(client: AsyncClient) -> None:
    token, _account_id = await _setup_user(client, "aidown@example.com")
    files = {"file": ("ticket.jpg", b"fake", "image/jpeg")}
    with _mock_storage_and_ai(extract_side_effect=AiUnavailableError("Ollama down")) as delete_mock:
        r = await client.post("/receipts/extract", files=files, headers=_auth(token))
    assert r.status_code == 502
    delete_mock.assert_called_once_with("fakekey/img.jpg")


async def test_confirm_creates_transaction_and_marks_confirmed(client: AsyncClient) -> None:
    token, account_id = await _setup_user(client, "confirm@example.com")
    files = {"file": ("ticket.jpg", b"fake", "image/jpeg")}
    with _mock_storage_and_ai():
        extract = await client.post("/receipts/extract", files=files, headers=_auth(token))
    receipt_id = extract.json()["receipt"]["id"]

    payload = {
        "account_id": account_id,
        "amount": "12.34",
        "occurred_at": "2026-04-15T13:45:00Z",
        "currency": "EUR",
        "description": "Mercadona",
    }
    r = await client.post(
        f"/receipts/{receipt_id}/confirm",
        json=payload,
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "confirmed"
    assert body["transaction_id"]

    # La transacción se creó como source=receipt y enlazada al receipt
    tx_list = await client.get("/transactions", headers=_auth(token))
    txs = tx_list.json()["items"]
    assert len(txs) == 1
    assert txs[0]["source"] == "receipt"
    assert txs[0]["receipt_id"] == receipt_id
    # PHASE-41: un ticket es gasto → flow=OUT (verdad del dinero, ADR-0004).
    # La categoría se hereda de la cascada: el seed trae la regla
    # MERCADONA→Supermercado (field=description) y el confirm pasa
    # description="Mercadona", así que la tx queda categorizada (antes: None).
    assert txs[0]["flow"] == "OUT"
    assert txs[0]["category_id"] is not None


async def test_confirm_twice_returns_409(client: AsyncClient) -> None:
    token, account_id = await _setup_user(client, "twice@example.com")
    files = {"file": ("ticket.jpg", b"fake", "image/jpeg")}
    with _mock_storage_and_ai():
        extract = await client.post("/receipts/extract", files=files, headers=_auth(token))
    receipt_id = extract.json()["receipt"]["id"]
    payload = {
        "account_id": account_id,
        "amount": "5.00",
        "occurred_at": "2026-04-15T00:00:00Z",
        "currency": "EUR",
    }
    r1 = await client.post(f"/receipts/{receipt_id}/confirm", json=payload, headers=_auth(token))
    assert r1.status_code == 200
    r2 = await client.post(f"/receipts/{receipt_id}/confirm", json=payload, headers=_auth(token))
    assert r2.status_code == 409


async def test_reject_marks_rejected_and_does_not_create_transaction(
    client: AsyncClient,
) -> None:
    token, _account_id = await _setup_user(client, "reject@example.com")
    files = {"file": ("ticket.jpg", b"fake", "image/jpeg")}
    with _mock_storage_and_ai():
        extract = await client.post("/receipts/extract", files=files, headers=_auth(token))
    receipt_id = extract.json()["receipt"]["id"]

    r = await client.post(f"/receipts/{receipt_id}/reject", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"

    tx_list = await client.get("/transactions", headers=_auth(token))
    assert tx_list.json()["total"] == 0


async def test_list_and_get_receipts(client: AsyncClient) -> None:
    token, _account_id = await _setup_user(client, "list@example.com")
    files = {"file": ("ticket.jpg", b"fake", "image/jpeg")}
    with _mock_storage_and_ai():
        await client.post("/receipts/extract", files=files, headers=_auth(token))
        await client.post("/receipts/extract", files=files, headers=_auth(token))

    r = await client.get("/receipts", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2

    rid = body["items"][0]["id"]
    r_one = await client.get(f"/receipts/{rid}", headers=_auth(token))
    assert r_one.status_code == 200


async def test_receipt_user_isolation(client: AsyncClient) -> None:
    token_a, _account_a = await _setup_user(client, "a@example.com")
    token_b, _account_b = await _setup_user(client, "b@example.com")
    files = {"file": ("ticket.jpg", b"fake", "image/jpeg")}
    with _mock_storage_and_ai():
        a_extract = await client.post("/receipts/extract", files=files, headers=_auth(token_a))
    rid = a_extract.json()["receipt"]["id"]

    # Usuario B no ve el recibo de A
    r = await client.get(f"/receipts/{rid}", headers=_auth(token_b))
    assert r.status_code == 404


async def test_get_blob_returns_image_bytes(client: AsyncClient) -> None:
    token, _account_id = await _setup_user(client, "blob@example.com")
    files = {"file": ("ticket.jpg", b"fake", "image/jpeg")}
    with _mock_storage_and_ai():
        extract = await client.post("/receipts/extract", files=files, headers=_auth(token))
    rid = extract.json()["receipt"]["id"]

    fake_bytes = b"\xff\xd8\xff\xe0image-bytes"
    with patch(
        "app.modules.personal_finance.receipts.router.storage.get_receipt",
        new_callable=AsyncMock,
        return_value=fake_bytes,
    ):
        r = await client.get(f"/receipts/{rid}/blob", headers=_auth(token))
    assert r.status_code == 200
    assert r.content == fake_bytes
    assert r.headers["content-type"].startswith("image/jpeg")


async def test_get_blob_isolated_per_user(client: AsyncClient) -> None:
    token_a, _account_a = await _setup_user(client, "ablob@example.com")
    token_b, _account_b = await _setup_user(client, "bblob@example.com")
    files = {"file": ("ticket.jpg", b"fake", "image/jpeg")}
    with _mock_storage_and_ai():
        a_extract = await client.post("/receipts/extract", files=files, headers=_auth(token_a))
    rid = a_extract.json()["receipt"]["id"]

    with patch(
        "app.modules.personal_finance.receipts.router.storage.get_receipt",
        new_callable=AsyncMock,
        return_value=b"x",
    ) as get_mock:
        r = await client.get(f"/receipts/{rid}/blob", headers=_auth(token_b))
    assert r.status_code == 404
    # No debe haber tocado MinIO si el receipt no es del usuario.
    get_mock.assert_not_called()


async def test_confirm_autocategorizes_via_bank_mapping(client: AsyncClient) -> None:
    """PHASE-41 — el comercio extraído ("Mercadona") resuelve a categoría vía
    una equivalencia aprendida (bank_mapping), sin que el usuario elija."""
    token, account_id = await _setup_user(client, "rcpt_map@example.com")
    cat = await _create_category(client, token, "Alimentación")
    m = await client.post(
        "/bank-mappings",
        json={"bank_concept": "Mercadona", "category_id": cat},
        headers=_auth(token),
    )
    assert m.status_code in (200, 201), m.text
    rid = await _extract_receipt_id(client, token)
    r = await _confirm(client, token, rid, account_id)  # sin category_id
    assert r.status_code == 200, r.text
    tx = await _only_tx(client, token)
    assert tx["category_id"] == cat
    assert tx["flow"] == "OUT"


async def test_confirm_autocategorizes_via_exact_name(client: AsyncClient) -> None:
    """PHASE-41 — sin mapping ni regla, el comercio casa por nombre de
    categoría exacto (normalizado, sin acentos)."""
    token, account_id = await _setup_user(client, "rcpt_name@example.com")
    cat = await _create_category(client, token, "Mercadona")
    rid = await _extract_receipt_id(client, token)
    r = await _confirm(client, token, rid, account_id)
    assert r.status_code == 200, r.text
    tx = await _only_tx(client, token)
    assert tx["category_id"] == cat


async def test_confirm_autocategorizes_via_rule(client: AsyncClient) -> None:
    """PHASE-41 — sin mapping ni nombre exacto, una regla `contains` resuelve
    el comercio."""
    token, account_id = await _setup_user(client, "rcpt_rule@example.com")
    cat = await _create_category(client, token, "Súper")
    rule = await client.post(
        "/category-rules",
        json={
            "pattern": "mercadona",
            "match_type": "contains",
            "field": "both",
            "category_id": cat,
        },
        headers=_auth(token),
    )
    assert rule.status_code in (200, 201), rule.text
    rid = await _extract_receipt_id(client, token)
    r = await _confirm(client, token, rid, account_id)
    assert r.status_code == 200, r.text
    tx = await _only_tx(client, token)
    assert tx["category_id"] == cat


async def test_confirm_explicit_category_overrides_cascade(client: AsyncClient) -> None:
    """PHASE-41 — si el usuario elige categoría a mano, gana sobre la cascada
    (no se ejecuta el autocategorizado)."""
    token, account_id = await _setup_user(client, "rcpt_override@example.com")
    mapped = await _create_category(client, token, "Alimentación")
    chosen = await _create_category(client, token, "Ocio")
    await client.post(
        "/bank-mappings",
        json={"bank_concept": "Mercadona", "category_id": mapped},
        headers=_auth(token),
    )
    rid = await _extract_receipt_id(client, token)
    r = await _confirm(client, token, rid, account_id, category_id=chosen)
    assert r.status_code == 200, r.text
    tx = await _only_tx(client, token)
    assert tx["category_id"] == chosen  # el override, no el mapeado


async def test_confirm_sets_flow_out_and_counts_in_balance(client: AsyncClient) -> None:
    """PHASE-41 — el ticket confirmado sale de la cuenta (flow=OUT): su importe
    resta del saldo. Antes quedaba flow=NULL (+ category NULL) y aportaba 0."""
    token, account_id = await _setup_user(client, "rcpt_balance@example.com")
    rid = await _extract_receipt_id(client, token)
    r = await _confirm(client, token, rid, account_id)
    assert r.status_code == 200, r.text
    balances = (await client.get("/accounts/balances", headers=_auth(token))).json()
    by_id = {b["account_id"]: b for b in balances["items"]}
    assert Decimal(by_id[account_id]["movements_balance"]) == Decimal("-12.34")


async def test_get_blob_storage_failure_returns_404(client: AsyncClient) -> None:
    from app.core.storage import StorageError

    token, _account_id = await _setup_user(client, "missing@example.com")
    files = {"file": ("ticket.jpg", b"fake", "image/jpeg")}
    with _mock_storage_and_ai():
        extract = await client.post("/receipts/extract", files=files, headers=_auth(token))
    rid = extract.json()["receipt"]["id"]

    with patch(
        "app.modules.personal_finance.receipts.router.storage.get_receipt",
        new_callable=AsyncMock,
        side_effect=StorageError("blob no existe"),
    ):
        r = await client.get(f"/receipts/{rid}/blob", headers=_auth(token))
    assert r.status_code == 404
