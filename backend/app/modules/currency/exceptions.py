"""Excepciones del módulo currency."""

from __future__ import annotations


class CurrencyError(Exception):
    """Base de las excepciones del módulo."""


class FrankfurterUnavailableError(CurrencyError):
    """frankfurter.app no responde o devuelve un error."""


class FrankfurterInvalidResponseError(CurrencyError):
    """frankfurter.app respondió con un payload que no encaja con lo esperado."""
