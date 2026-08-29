"""De dónde salió la vara con la que se midió cada métrica (PHASE-44.24.C).

Desde el motor 1.7.0 la procedencia **viaja dentro del run** y aquí sólo se lee.
Lo que este módulo resuelve es el otro caso: los runs anteriores, que no la
registran y para los que hay que derivarla — diciendo que es una derivación.

Seis valores, y cada uno responde a una pregunta distinta que la pantalla
necesita para no mentir:

- `not_recorded` — el run no registró el corte de ESTA métrica. No es «pre-44.9»:
  un run de 1.3.0 tiene `thresholds_used` y no tiene S7 ni S8, porque el motor de
  entonces no las emitía. La pantalla enseña el corte del catálogo de HOY, y
  tiene que decir que es el de hoy y no el que se aplicó.
- `not_applicable` — la vara no aplica a este (sector × norma). Se comprueba
  ANTES de indexar ningún default: preguntar por la procedencia de un corte que
  el motor descartó a propósito no tiene sentido.
- `uncalibrated` — los cortes son US-GAAP sobre cuentas que no lo son.
- `generic` / `sector` / `financial` / `table` — lo que el run registró, o lo
  que se deriva de él.
- `earlier_calibration` — sólo en runs sin `origin`: los cortes no coinciden ni
  con el genérico ni con el perfil de hoy, así que son de una calibración
  anterior. Sin este valor, cualquier recalibración genérica posterior al run se
  leería como «banda sectorial» — «perfil actual: unknown» para una empresa sin
  perfil, que es el falso «esto parece un bug» que la fase viene a quitar.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from app.modules.investment.analysis.engine.sector_profiles import UNCALIBRATED
from app.modules.investment.analysis.engine.types import ThresholdSpec
from app.modules.investment.analysis.presentation.rehydrate import recorded_origin
from app.modules.investment.enums import SectorInternal

Origin = Literal[
    "generic",
    "sector",
    "financial",
    "table",
    "earlier_calibration",
    "uncalibrated",
    "not_applicable",
    "not_recorded",
]


@dataclass(frozen=True)
class ThresholdProfile:
    """Qué perfil gobierna a este valor HOY, resuelto por el servidor.

    Se emite entero —el perfil efectivo y los tres datos que lo determinan— en
    vez de una etiqueta suelta, porque componerla en la pantalla con
    `security.sector` es **falso para toda entidad financiera clasificada en
    otro sector**: `profile_for` fusiona el perfil financiero por encima del
    sectorial, y por el prefijo SIC 67 ése es el estado normal de las socimis
    del catálogo.
    """

    effective: str
    sector: str
    is_financial: bool
    is_reit: bool


def profile_of(sector: SectorInternal, *, is_financial: bool, is_reit: bool) -> ThresholdProfile:
    """El perfil efectivo de un valor, con lo que lo determina."""
    effective = (
        SectorInternal.FINANCIALS.value
        if (is_financial or sector is SectorInternal.FINANCIALS)
        else sector.value
    )
    return ThresholdProfile(
        effective=effective, sector=sector.value, is_financial=is_financial, is_reit=is_reit
    )


def threshold_origin(
    key: str,
    *,
    persisted: Mapping[str, Any] | None,
    used: Mapping[str, ThresholdSpec],
    generic: Mapping[str, ThresholdSpec],
    profile: Mapping[str, ThresholdSpec],
) -> Origin:
    """La procedencia del corte de una métrica en un run concreto.

    `persisted` es el JSONB crudo —de donde se lee si el run la registró— y
    `used` su versión rehidratada. `generic` y `profile` son las resoluciones de
    HOY, y sólo se usan para derivar cuando el run no registró nada.

    El orden de las comprobaciones importa: `not_recorded` y `not_applicable` van
    antes que cualquier indexación de defaults, porque preguntar por el corte de
    algo que no se midió —o que el motor descartó— no tiene respuesta.
    """
    spec = used.get(key)
    if spec is None:
        return "not_recorded"
    if not spec.applies:
        return "not_applicable"
    if spec.model_variant == UNCALIBRATED:
        return "uncalibrated"

    registered = recorded_origin(persisted, key)
    if registered is not None:
        # Motor ≥ 1.7.0: no se infiere nada, se lee.
        return registered  # type: ignore[return-value]

    # Run anterior: se deriva contra la calibración de hoy, y quien lo pinte
    # tiene que declarar que es una derivación.
    if _same_cuts(spec, generic.get(key)):
        return "generic"
    if _same_cuts(spec, profile.get(key)):
        return "sector"
    return "earlier_calibration"


def _same_cuts(spec: ThresholdSpec, other: ThresholdSpec | None) -> bool:
    """Los cuatro cortes y la dirección, comparados como NÚMERO.

    Nunca como cadena: lo persistido llega con la escala de la columna
    (`"0.600000"`) y el catálogo tiene `Decimal("0.6")`. Comparar el texto
    marcaría como «calibrado distinto» todo run producido con la tabla sembrada.
    """
    if other is None:
        return False
    return (
        spec.direction == other.direction
        and spec.low_alarm == other.low_alarm
        and spec.low_ok == other.low_ok
        and spec.high_ok == other.high_ok
        and spec.high_alarm == other.high_alarm
    )
