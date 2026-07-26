"""Fábrica del adapter de fundamentales (PHASE-44.7).

El adapter EDGAR se construye SIN conocer `settings` (recibe identidad y
`cache_dir` explícitos), para que siga siendo puro y testeable. Este módulo es el
único que lo cablea a la configuración del backend, y expone una dependencia
FastAPI (`get_fundamentals_adapter`) que los tests pueden sobreescribir con un
doble sin tocar la red.
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.modules.investment.fundamentals.adapters.base import FundamentalsAdapter
from app.modules.investment.fundamentals.adapters.edgar import EdgarAdapter

# factory.py → adapters → fundamentals → investment → modules → app → backend
_BACKEND_ROOT = Path(__file__).resolve().parents[5]


def _cache_dir() -> Path:
    """`EDGAR_CACHE_DIR`, resuelta contra la raíz del backend si es relativa."""
    configured = Path(settings.edgar_cache_dir)
    return configured if configured.is_absolute() else _BACKEND_ROOT / configured


def build_edgar_adapter() -> EdgarAdapter:
    """Un `EdgarAdapter` cableado a la configuración del backend.

    Construirlo NO toca la red ni exige identidad: la identidad sólo se exige al
    salir a la SEC (ver `EdgarAdapter._require_identity`), así que se puede
    reingerir desde la cache sin `EDGAR_IDENTITY`.
    """
    return EdgarAdapter(
        identity=settings.edgar_identity,
        cache_dir=_cache_dir(),
        timeout_seconds=settings.edgar_timeout_seconds,
    )


def get_fundamentals_adapter() -> FundamentalsAdapter:
    """Dependencia FastAPI. Los endpoints que resuelven/ingieren la piden con
    `Depends(get_fundamentals_adapter)`; los tests la sobreescriben con un doble
    (`app.dependency_overrides[get_fundamentals_adapter] = ...`) para no tocar la
    SEC."""
    return build_edgar_adapter()
