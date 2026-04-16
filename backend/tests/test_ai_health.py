"""Tests del endpoint /ai/health con Ollama mockeado."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient


async def test_ai_health_ollama_up(client: AsyncClient) -> None:
    """Cuando Ollama responde y el modelo está disponible."""
    with (
        patch(
            "app.modules.ai.client.ping",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.modules.ai.client.is_model_available",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        response = await client.get("/ai/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["ollama"] == "connected"
    assert body["model_available"] is True


async def test_ai_health_ollama_down(client: AsyncClient) -> None:
    """Cuando Ollama no responde."""
    with patch(
        "app.modules.ai.client.ping",
        new_callable=AsyncMock,
        return_value=False,
    ):
        response = await client.get("/ai/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["ollama"] == "unavailable"
    assert body["model_available"] is False


async def test_ai_health_model_missing(client: AsyncClient) -> None:
    """Cuando Ollama responde pero el modelo no está descargado."""
    with (
        patch(
            "app.modules.ai.client.ping",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.modules.ai.client.is_model_available",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        response = await client.get("/ai/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["ollama"] == "connected"
    assert body["model_available"] is False
