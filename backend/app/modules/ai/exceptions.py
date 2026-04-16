"""Excepciones del módulo de IA."""

from __future__ import annotations


class AiError(Exception):
    """Base de todas las excepciones del módulo ai."""


class AiUnavailableError(AiError):
    """Ollama no responde o no está arrancado."""


class AiTimeoutError(AiError):
    """La inferencia ha excedido el timeout configurado."""


class AiInvalidOutputError(AiError):
    """La respuesta del modelo no se pudo parsear con el schema esperado."""
