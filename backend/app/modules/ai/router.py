"""Router del módulo ai — endpoints de sistema."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.modules.ai import client
from app.modules.ai.schemas import AiHealthResponse

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/health", response_model=AiHealthResponse)
async def ai_health() -> AiHealthResponse:
    """Health check del runtime de IA local (Ollama).

    Comprueba si Ollama está respondiendo y si el modelo de visión
    configurado está disponible.
    """
    ollama_up = await client.ping()

    model_available = False
    if ollama_up:
        model_available = await client.is_model_available()

    return AiHealthResponse(
        status="ok" if ollama_up else "degraded",
        ollama="connected" if ollama_up else "unavailable",
        model=settings.ollama_vision_model,
        model_available=model_available,
    )
