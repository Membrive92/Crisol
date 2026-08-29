"""De JSONB persistido a `ThresholdSpec` (PHASE-44.24.C).

`AnalysisRun.thresholds_used` guarda los cortes como TEXTO —`to_json_safe`
convierte `Decimal → str` para no perder precisión— y, cuando la spec vino de la
tabla, con la escala de la columna: `Numeric(12, 6)` produce `"0.600000"` donde
el motor tiene `Decimal("0.6")`.

Ese detalle es el que hace que esta función exista en vez de comparar los
diccionarios tal cual. Iguales como número, distintos como cadena: cualquier
comparación textual contra el catálogo marcaría **todo** run producido con la
tabla sembrada como «calibrado distinto», que es justo lo contrario de lo que se
quiere decir.

El código estaba escrito a mano dentro de un test (`test_investment_analysis`),
que es donde nadie lo encuentra cuando lo necesita en producción.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from app.modules.investment.analysis.engine.types import ThresholdSpec
from app.modules.investment.enums import ThresholdDirection


def _decimal(value: Any) -> Decimal | None:
    """Un corte persistido a `Decimal`. `None` si falta o no es un número.

    No revienta ante basura: un run es un documento de años atrás y un campo
    ilegible no puede tumbar la pantalla entera. Se pierde ese corte, que la
    capa de arriba ya sabe tratar como «sin banda».
    """
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def rehydrate_thresholds(persisted: Mapping[str, Any] | None) -> dict[str, ThresholdSpec]:
    """`thresholds_used` → specs comparables como número.

    Las entradas que no se puedan leer se descartan en vez de aparecer a medias:
    una spec con la dirección perdida no puede bandear nada, y fingir que sí es
    peor que no tenerla. Un run anterior a PHASE-44.9 trae `{}` y devuelve `{}`,
    que es la señal de «este run no registró con qué se midió».
    """
    if not persisted:
        return {}
    specs: dict[str, ThresholdSpec] = {}
    for key, raw in persisted.items():
        if not isinstance(raw, Mapping):
            continue
        try:
            direction = ThresholdDirection(raw["direction"])
        except (KeyError, ValueError):
            continue
        origin = raw.get("origin")
        applies = bool(raw.get("applies", True))
        reason = raw.get("not_applicable_reason")
        if not applies and not reason:
            # `ThresholdSpec` exige un motivo cuando la vara no aplica —un «N/A»
            # mudo es indistinguible de un fallo de cálculo— y hace cumplir el
            # invariante lanzando. Aquí no se puede lanzar: esto lee un documento
            # de hace años, y un campo que falte no puede tumbar la pantalla
            # entera. Se declara la ausencia, que es lo honesto y además cumple
            # el invariante por el motivo por el que existe.
            reason = "este análisis no registró por qué la vara no aplicaba"
        specs[key] = ThresholdSpec(
            metric_key=str(raw.get("metric_key") or key),
            direction=direction,
            low_alarm=_decimal(raw.get("low_alarm")),
            low_ok=_decimal(raw.get("low_ok")),
            high_ok=_decimal(raw.get("high_ok")),
            high_alarm=_decimal(raw.get("high_alarm")),
            model_variant=raw.get("model_variant"),
            applies=applies,
            # `origin` llegó en el motor 1.7.0. Ausente NO es `generic`: en los
            # runs anteriores la procedencia no se registraba, y quien lea esto
            # tiene que poder distinguir «era la genérica» de «no se sabe». El
            # centinela es que la clave no venga; el default del dataclass sólo
            # aplica a lo que este módulo construye de cero.
            **({"origin": origin} if origin in ("generic", "sector", "financial", "table") else {}),
            not_applicable_reason=reason,
        )
    return specs


def recorded_origin(persisted: Mapping[str, Any] | None, key: str) -> str | None:
    """La procedencia que el RUN registró, o `None` si no la registró.

    Se pregunta al JSONB crudo y no a la spec rehidratada a propósito: allí el
    campo tiene un default (`generic`) y no se puede distinguir de una ausencia.
    """
    if not persisted:
        return None
    raw = persisted.get(key)
    if not isinstance(raw, Mapping):
        return None
    origin = raw.get("origin")
    return origin if origin in ("generic", "sector", "financial", "table") else None
