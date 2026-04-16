"""Schemas Pydantic del módulo ai."""

from __future__ import annotations

from pydantic import BaseModel


class AiHealthResponse(BaseModel):
    """Respuesta del endpoint /ai/health."""

    status: str
    ollama: str
    model: str
    model_available: bool
