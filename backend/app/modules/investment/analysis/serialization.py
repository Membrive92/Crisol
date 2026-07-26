"""Serialización de resultados del engine a JSONB (PHASE-44.7).

El engine devuelve dataclasses inmutables con `Decimal`, `date`, enums y tuplas
dentro. Las columnas JSONB de `AnalysisRun` necesitan tipos JSON-safe. Este
convertidor recursivo es la única frontera donde los tipos del engine se aplanan:
`Decimal → str` (nunca float, para no perder precisión), `date → isoformat`,
`Enum → .value`, dataclass → dict, tupla/set → lista.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any


def to_json_safe(obj: Any) -> Any:
    """Convierte cualquier salida del engine en algo serializable a JSONB."""
    # `bool` es subclase de `int`: ambos se devuelven tal cual (JSON los admite).
    if obj is None or isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_json_safe(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, Mapping):
        return {str(key): to_json_safe(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_json_safe(value) for value in obj]
    if isinstance(obj, float):  # el engine no emite floats, pero por si acaso: sin perder precisión
        return str(Decimal(str(obj)))
    return str(obj)
