"""Tests de `ai.service` con el cliente Ollama mockeado.

Cubre `extract_receipt` (ticket fotográfico) y
`extract_bank_statement_page` (página de extracto bancario para el
fallback de visión PDF).
"""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.ai import service as ai_service
from app.modules.ai.exceptions import AiInvalidOutputError

_VALID_RESPONSE = json.dumps(
    {
        "merchant": "Mercadona",
        "occurred_at": "2026-04-15T13:45:00",
        "currency": "EUR",
        "total": "12.34",
        "tax": "1.23",
        "line_items": [
            {"description": "Pan", "quantity": "1", "unit_price": "1.00", "total": "1.00"},
            {"description": "Leche", "quantity": "2", "unit_price": "1.20", "total": "2.40"},
        ],
        "raw_text": "Ticket Mercadona ...",
    }
)


async def test_extract_receipt_returns_typed_extraction() -> None:
    with patch(
        "app.modules.ai.client.generate_with_image",
        new_callable=AsyncMock,
        return_value=_VALID_RESPONSE,
    ):
        result = await ai_service.extract_receipt(b"fake-image-bytes")

    assert result.merchant == "Mercadona"
    assert result.currency == "EUR"
    assert str(result.total) == "12.34"
    assert len(result.line_items) == 2
    assert result.line_items[0].description == "Pan"


async def test_extract_receipt_invalid_json_raises() -> None:
    with patch(
        "app.modules.ai.client.generate_with_image",
        new_callable=AsyncMock,
        return_value="not json {",
    ), pytest.raises(AiInvalidOutputError):
        await ai_service.extract_receipt(b"fake")


async def test_extract_receipt_invalid_schema_raises() -> None:
    """`currency` con menos de 3 letras incumple el schema."""
    with patch(
        "app.modules.ai.client.generate_with_image",
        new_callable=AsyncMock,
        return_value=json.dumps({"currency": "X"}),
    ), pytest.raises(AiInvalidOutputError):
        await ai_service.extract_receipt(b"fake")


async def test_extract_receipt_total_null_is_accepted() -> None:
    """El modelo puede devolver `total: null` cuando no consigue leerlo;
    el usuario lo rellenará en el form de confirmación."""
    response = json.dumps(
        {
            "merchant": "Mercadona",
            "total": None,
            "currency": "EUR",
            "line_items": [],
        }
    )
    with patch(
        "app.modules.ai.client.generate_with_image",
        new_callable=AsyncMock,
        return_value=response,
    ):
        extraction = await ai_service.extract_receipt(b"fake")
    assert extraction.total is None
    assert extraction.merchant == "Mercadona"


async def test_extract_receipt_normalizes_spanish_decimals_and_dates() -> None:
    """El modelo a veces devuelve `27,66` y `19/02/26T12:31`; el schema
    normaliza ambos antes de validar."""
    response = json.dumps(
        {
            "merchant": "Fcia. San Pedro",
            "occurred_at": "19/02/26T12:31",
            "currency": "EUR",
            "total": "27,66",
            "tax": "1,06",
            "line_items": [
                {
                    "description": "SPRAAXN 200 MG",
                    "quantity": "1",
                    "unit_price": "9,21",
                    "total": "27,66",
                }
            ],
        }
    )
    with patch(
        "app.modules.ai.client.generate_with_image",
        new_callable=AsyncMock,
        return_value=response,
    ):
        extraction = await ai_service.extract_receipt(b"fake")
    assert extraction.total == Decimal("27.66")
    assert extraction.tax == Decimal("1.06")
    assert extraction.occurred_at is not None
    assert extraction.occurred_at.year == 2026
    assert extraction.occurred_at.month == 2
    assert extraction.occurred_at.day == 19
    assert extraction.line_items[0].unit_price == Decimal("9.21")
    assert extraction.line_items[0].total == Decimal("27.66")


async def test_extract_receipt_normalizes_thousands_separator() -> None:
    """`1.234,56` (formato español con miles) → `1234.56`."""
    response = json.dumps(
        {
            "merchant": "Big Receipt",
            "currency": "EUR",
            "total": "1.234,56",
            "line_items": [],
        }
    )
    with patch(
        "app.modules.ai.client.generate_with_image",
        new_callable=AsyncMock,
        return_value=response,
    ):
        extraction = await ai_service.extract_receipt(b"fake")
    assert extraction.total == Decimal("1234.56")


# ─────────────────────────────────────
# Bank statement page (fallback PDF)
# ─────────────────────────────────────


async def test_extract_bank_statement_page_returns_rows() -> None:
    response = json.dumps(
        {
            "rows": [
                {
                    "description": "Alquiler",
                    "amount": "750.00",
                    "occurred_at": "2026-04-01",
                },
                {
                    "description": "Nómina",
                    "amount": "1850.50",
                    "occurred_at": "2026-04-05",
                },
            ]
        }
    )
    with patch(
        "app.modules.ai.client.generate_with_image",
        new_callable=AsyncMock,
        return_value=response,
    ):
        rows = await ai_service.extract_bank_statement_page(b"fake-image")

    assert len(rows) == 2
    assert rows[0].description == "Alquiler"
    assert rows[0].amount == Decimal("750.00")
    assert rows[1].occurred_at == "2026-04-05"


async def test_extract_bank_statement_page_empty_rows_ok() -> None:
    """Página sin tabla de movimientos: rows vacío, no error."""
    with patch(
        "app.modules.ai.client.generate_with_image",
        new_callable=AsyncMock,
        return_value=json.dumps({"rows": []}),
    ):
        rows = await ai_service.extract_bank_statement_page(b"fake-image")
    assert rows == []


async def test_extract_bank_statement_page_invalid_json_raises() -> None:
    with patch(
        "app.modules.ai.client.generate_with_image",
        new_callable=AsyncMock,
        return_value="not json",
    ), pytest.raises(AiInvalidOutputError):
        await ai_service.extract_bank_statement_page(b"fake")


async def test_extract_bank_statement_page_negative_amount_rejected() -> None:
    """El schema obliga a importes positivos: el modelo no debe colar negativos."""
    response = json.dumps(
        {
            "rows": [
                {"description": "X", "amount": "-10", "occurred_at": "2026-04-01"},
            ]
        }
    )
    with patch(
        "app.modules.ai.client.generate_with_image",
        new_callable=AsyncMock,
        return_value=response,
    ), pytest.raises(AiInvalidOutputError):
        await ai_service.extract_bank_statement_page(b"fake")
