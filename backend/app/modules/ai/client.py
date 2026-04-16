"""Cliente HTTP async contra Ollama.

Este es el ÚNICO archivo del proyecto que conoce la URL de Ollama y habla
con su API HTTP. Ningún otro módulo importa httpx para hablar con Ollama.
"""

from __future__ import annotations

import httpx

from app.core.config import settings
from app.modules.ai.exceptions import AiTimeoutError, AiUnavailableError


async def ping() -> bool:
    """Comprueba si Ollama está respondiendo."""
    try:
        async with httpx.AsyncClient(
            base_url=settings.ollama_base_url,
            timeout=5.0,
        ) as client:
            response = await client.get("/")
            return response.status_code == 200
    except (httpx.ConnectError, httpx.ConnectTimeout):
        return False


async def list_models() -> list[str]:
    """Devuelve los nombres de los modelos disponibles en Ollama.

    Raises:
        AiUnavailable: Ollama no responde.
        AiTimeout: la petición excede el timeout.
    """
    try:
        async with httpx.AsyncClient(
            base_url=settings.ollama_base_url,
            timeout=10.0,
        ) as client:
            response = await client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
    except (httpx.ConnectError, httpx.ConnectTimeout) as e:
        raise AiUnavailableError("Ollama no responde") from e
    except httpx.ReadTimeout as e:
        raise AiTimeoutError("Timeout listando modelos") from e


async def is_model_available(model: str | None = None) -> bool:
    """Comprueba si el modelo de visión está descargado en Ollama."""
    target = model or settings.ollama_vision_model
    try:
        models = await list_models()
    except (AiUnavailableError, AiTimeoutError):
        return False
    return any(target in m for m in models)
