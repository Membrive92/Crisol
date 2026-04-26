"""Tests de `ai.service.extract_receipt` con el cliente Ollama mockeado."""

from __future__ import annotations

import json
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
    ):
        with pytest.raises(AiInvalidOutputError):
            await ai_service.extract_receipt(b"fake")


async def test_extract_receipt_invalid_schema_raises() -> None:
    """Falta el campo `total` (obligatorio)."""
    with patch(
        "app.modules.ai.client.generate_with_image",
        new_callable=AsyncMock,
        return_value=json.dumps({"merchant": "X"}),
    ):
        with pytest.raises(AiInvalidOutputError):
            await ai_service.extract_receipt(b"fake")
