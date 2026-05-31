"""Cliente HTTP async contra Ollama.

Este es el ÚNICO archivo del proyecto que conoce la URL de Ollama y habla
con su API HTTP. Ningún otro módulo importa httpx para hablar con Ollama.
"""

from __future__ import annotations

import asyncio
import base64
import io
from typing import Any

import httpx
from PIL import Image, ImageOps, UnidentifiedImageError
from PIL.Image import DecompressionBombError

from app.core.config import settings
from app.modules.ai.exceptions import AiError, AiTimeoutError, AiUnavailableError

# Cota anti decompression-bomb: Pillow lanza DecompressionBombError al abrir
# imágenes que declaran más píxeles que esto (un recibo real cabe de sobra en
# 50 MP). Evita el agotamiento de memoria al redimensionar (AUDIT-2026-05).
Image.MAX_IMAGE_PIXELS = 50_000_000

# Tamaño máximo del lado largo al pasar imágenes al modelo de visión. Las
# fotos de móvil llegan a 4032 px y producen miles de tokens de visión que
# disparan el tiempo de inferencia (>120 s en CPU) y a veces hacen que el
# runner devuelva 500 al exceder la KV cache. 1280 px conserva detalle
# suficiente para leer tickets y reduce la inferencia a ~30-60 s.
_MAX_IMAGE_LONG_SIDE = 1280
_JPEG_QUALITY = 85


def _downscale_for_vision(image: bytes) -> bytes:
    """Reduce la imagen al lado largo máximo si excede `_MAX_IMAGE_LONG_SIDE`.

    Devuelve los bytes originales sin tocar si:
    - la imagen ya cabe,
    - Pillow no puede abrirla (formato raro): que el modelo lo intente igual.

    El blob original se guarda íntegro en MinIO antes de llegar aquí — esta
    reducción es sólo para alimentar al modelo.
    """
    try:
        with Image.open(io.BytesIO(image)) as img:
            oriented = ImageOps.exif_transpose(img) or img
            w, h = oriented.size
            if max(w, h) <= _MAX_IMAGE_LONG_SIDE:
                return image
            oriented.thumbnail(
                (_MAX_IMAGE_LONG_SIDE, _MAX_IMAGE_LONG_SIDE),
                Image.Resampling.LANCZOS,
            )
            if oriented.mode not in {"RGB", "L"}:
                oriented = oriented.convert("RGB")
            buf = io.BytesIO()
            oriented.save(buf, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
            return buf.getvalue()
    except DecompressionBombError as e:
        # Imagen-bomba (dimensiones declaradas enormes) — rechazo limpio en
        # vez de agotar memoria o pasarla a Ollama (AUDIT-2026-05).
        raise AiError("Imagen rechazada: dimensiones excesivas.") from e
    except (OSError, UnidentifiedImageError):
        return image


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
    timeout_seconds: int | None = None,
) -> str:
    """Llama a `POST /api/generate` con el modelo de visión.

    Devuelve el campo `response` (string) tal cual lo entrega el modelo.
    El parser/validador de la respuesta vive en `ai.service`. La imagen
    se pasa como base64 (la API de Ollama lo acepta así).

    `timeout_seconds` permite al caller subir el default global (típicamente
    120s suficiente para tickets) cuando la imagen tiene mucho texto y la
    inferencia tarda más — caso típico: páginas de extracto bancario.

    Raises:
        AiUnavailable: Ollama no responde.
        AiTimeout: la inferencia excede el timeout configurado.
    """
    target = model or settings.ollama_vision_model
    # El resize Pillow es CPU-bound y bloqueante → threadpool (AUDIT-2026-05).
    downscaled = await asyncio.to_thread(_downscale_for_vision, image)
    encoded = base64.b64encode(downscaled).decode("ascii")
    payload: dict[str, Any] = {
        "model": target,
        "prompt": prompt,
        "images": [encoded],
        "stream": False,
    }
    if json_mode:
        payload["format"] = "json"

    effective_timeout = float(timeout_seconds or settings.ollama_timeout_seconds)
    try:
        async with httpx.AsyncClient(
            base_url=settings.ollama_base_url,
            timeout=effective_timeout,
        ) as client:
            response = await client.post("/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return str(data.get("response", ""))
    except (httpx.ConnectError, httpx.ConnectTimeout) as e:
        raise AiUnavailableError("Ollama no responde") from e
    except httpx.ReadTimeout as e:
        raise AiTimeoutError("Timeout de inferencia") from e
    except httpx.HTTPStatusError as e:
        # Ollama puede devolver 500 cuando la KV cache se queda corta o el
        # runner aborta con OOM. Lo tratamos como "no disponible" para que
        # el caller (receipts service) limpie blobs y devuelva 502.
        raise AiUnavailableError(f"Ollama error {e.response.status_code}") from e


async def generate_text(
    *,
    prompt: str,
    model: str | None = None,
    json_mode: bool = True,
    timeout_seconds: int | None = None,
) -> str:
    """Llama a `POST /api/generate` con prompt de texto puro (sin imagen).

    Usado por flujos como sugerencia de categorías por concepto del
    banco (PHASE-20+). Mismo manejo de timeouts y errores que
    `generate_with_image`.
    """
    target = model or settings.ollama_text_model
    payload: dict[str, Any] = {
        "model": target,
        "prompt": prompt,
        "stream": False,
    }
    if json_mode:
        payload["format"] = "json"

    effective_timeout = float(timeout_seconds or settings.ollama_timeout_seconds)
    try:
        async with httpx.AsyncClient(
            base_url=settings.ollama_base_url,
            timeout=effective_timeout,
        ) as client:
            response = await client.post("/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return str(data.get("response", ""))
    except (httpx.ConnectError, httpx.ConnectTimeout) as e:
        raise AiUnavailableError("Ollama no responde") from e
    except httpx.ReadTimeout as e:
        raise AiTimeoutError("Timeout de inferencia") from e
    except httpx.HTTPStatusError as e:
        raise AiUnavailableError(f"Ollama error {e.response.status_code}") from e
