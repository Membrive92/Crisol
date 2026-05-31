"""Tests del endpoint /ai/health con Ollama mockeado."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient


async def _auth_header(client: AsyncClient) -> dict[str, str]:
    """Registra un usuario y devuelve la cabecera Authorization.

    AUDIT-2026-05: /ai/health pasó a requerir autenticación (no exponer el
    estado/modelo de la IA local a anónimos)."""
    r = await client.post(
        "/auth/register",
        json={
            "email": "aihealth@example.com",
            "password": "SecurePass123",
            "display_name": "AI",
        },
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_ai_health_requires_auth(client: AsyncClient) -> None:
    """Sin token → 401 (no se filtra el estado de la IA a anónimos)."""
    response = await client.get("/ai/health")
    assert response.status_code == 401


async def test_ai_health_ollama_up(client: AsyncClient) -> None:
    """Cuando Ollama responde y el modelo está disponible."""
    headers = await _auth_header(client)
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
        response = await client.get("/ai/health", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["ollama"] == "connected"
    assert body["model_available"] is True


async def test_ai_health_ollama_down(client: AsyncClient) -> None:
    """Cuando Ollama no responde."""
    headers = await _auth_header(client)
    with patch(
        "app.modules.ai.client.ping",
        new_callable=AsyncMock,
        return_value=False,
    ):
        response = await client.get("/ai/health", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["ollama"] == "unavailable"
    assert body["model_available"] is False


async def test_ai_health_model_missing(client: AsyncClient) -> None:
    """Cuando Ollama responde pero el modelo no está descargado."""
    headers = await _auth_header(client)
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
        response = await client.get("/ai/health", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["ollama"] == "connected"
    assert body["model_available"] is False
