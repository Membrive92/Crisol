"""Tests del módulo receipts (router + service) con mocks de IA y MinIO."""

from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient

from app.modules.ai.schemas import ReceiptExtraction, ReceiptLineItem
from app.modules.ai.exceptions import AiUnavailableError


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
    delete_mock = MagicMock(return_value=None)

    extract_kwargs: dict[str, Any] = {}
    if extract_side_effect is not None:
        extract_kwargs["side_effect"] = extract_side_effect
    else:
        extract_kwargs["return_value"] = extraction or _sample_extraction()

    with (
        patch("app.modules.receipts.service.storage.put_receipt", return_value="fakekey/img.jpg"),
        patch("app.modules.receipts.service.storage.delete_receipt", delete_mock),
        patch(
            "app.modules.receipts.service.ai_service.extract_receipt",
            new_callable=AsyncMock,
            **extract_kwargs,
        ),
    ):
        yield delete_mock


async def _setup_user(client: AsyncClient, email: str = "rcpt@example.com") -> str:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Rcpt"},
    )
    return str(r.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_extract_creates_pending_receipt(client: AsyncClient) -> None:
    token = await _setup_user(client)
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
    token = await _setup_user(client, "badimg@example.com")
    files = {"file": ("ticket.gif", b"\x00\x00", "image/gif")}
    with _mock_storage_and_ai():
        r = await client.post("/receipts/extract", files=files, headers=_auth(token))
    assert r.status_code == 400


async def test_extract_empty_payload_rejected(client: AsyncClient) -> None:
    token = await _setup_user(client, "empty@example.com")
    files = {"file": ("ticket.jpg", b"", "image/jpeg")}
    with _mock_storage_and_ai():
        r = await client.post("/receipts/extract", files=files, headers=_auth(token))
    assert r.status_code == 400


async def test_extract_ai_unavailable_cleans_blob(client: AsyncClient) -> None:
    token = await _setup_user(client, "aidown@example.com")
    files = {"file": ("ticket.jpg", b"fake", "image/jpeg")}
    with _mock_storage_and_ai(
        extract_side_effect=AiUnavailableError("Ollama down")
    ) as delete_mock:
        r = await client.post("/receipts/extract", files=files, headers=_auth(token))
    assert r.status_code == 502
    delete_mock.assert_called_once_with("fakekey/img.jpg")


async def test_confirm_creates_transaction_and_marks_confirmed(client: AsyncClient) -> None:
    token = await _setup_user(client, "confirm@example.com")
    files = {"file": ("ticket.jpg", b"fake", "image/jpeg")}
    with _mock_storage_and_ai():
        extract = await client.post("/receipts/extract", files=files, headers=_auth(token))
    receipt_id = extract.json()["receipt"]["id"]

    payload = {
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


async def test_confirm_twice_returns_409(client: AsyncClient) -> None:
    token = await _setup_user(client, "twice@example.com")
    files = {"file": ("ticket.jpg", b"fake", "image/jpeg")}
    with _mock_storage_and_ai():
        extract = await client.post("/receipts/extract", files=files, headers=_auth(token))
    receipt_id = extract.json()["receipt"]["id"]
    payload = {
        "amount": "5.00",
        "occurred_at": "2026-04-15T00:00:00Z",
        "currency": "EUR",
    }
    r1 = await client.post(
        f"/receipts/{receipt_id}/confirm", json=payload, headers=_auth(token)
    )
    assert r1.status_code == 200
    r2 = await client.post(
        f"/receipts/{receipt_id}/confirm", json=payload, headers=_auth(token)
    )
    assert r2.status_code == 409


async def test_reject_marks_rejected_and_does_not_create_transaction(
    client: AsyncClient,
) -> None:
    token = await _setup_user(client, "reject@example.com")
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
    token = await _setup_user(client, "list@example.com")
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
    token_a = await _setup_user(client, "a@example.com")
    token_b = await _setup_user(client, "b@example.com")
    files = {"file": ("ticket.jpg", b"fake", "image/jpeg")}
    with _mock_storage_and_ai():
        a_extract = await client.post("/receipts/extract", files=files, headers=_auth(token_a))
    rid = a_extract.json()["receipt"]["id"]

    # Usuario B no ve el recibo de A
    r = await client.get(f"/receipts/{rid}", headers=_auth(token_b))
    assert r.status_code == 404
