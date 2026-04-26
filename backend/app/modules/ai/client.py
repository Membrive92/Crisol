"""Cliente HTTP async contra Ollama.

Este es el ÚNICO archivo del proyecto que conoce la URL de Ollama y habla
con su API HTTP. Ningún otro módulo importa httpx para hablar con Ollama.
"""

from __future__ import annotations

import base64
from typing import Any

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


async def generate_with_image(
    *,
    prompt: str,
    image: bytes,
    model: str | None = None,
    json_mode: bool = True,
) -> str:
    """Llama a `POST /api/generate` con el modelo de visión.

    Devuelve el campo `response` (string) tal cual lo entrega el modelo.
    El parser/validador de la respuesta vive en `ai.service`. La imagen
    se pasa como base64 (la API de Ollama lo acepta así).

    Raises:
        AiUnavailable: Ollama no responde.
        AiTimeout: la inferencia excede el timeout configurado.
    """
    target = model or settings.ollama_vision_model
    encoded = base64.b64encode(image).decode("ascii")
    payload: dict[str, Any] = {
        "model": target,
        "prompt": prompt,
        "images": [encoded],
        "stream": False,
    }
    if json_mode:
        payload["format"] = "json"

    try:
        async with httpx.AsyncClient(
            base_url=settings.ollama_base_url,
            timeout=float(settings.ollama_timeout_seconds),
        ) as client:
            response = await client.post("/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return str(data.get("response", ""))
    except (httpx.ConnectError, httpx.ConnectTimeout) as e:
        raise AiUnavailableError("Ollama no responde") from e
    except httpx.ReadTimeout as e:
        raise AiTimeoutError("Timeout de inferencia") from e
