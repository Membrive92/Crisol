"""Hechos XBRL → `CanonicalStatement` (PHASE-44.6, ARCHITECTURE §3.3).

La frontera de la ingesta: entra un diccionario plano de hechos de UN ejercicio
—ya anclados al cierre fiscal por el adapter— y sale el estado canónico que
consume el engine, con su procedencia partida a partida y la traza de qué
concepto alimentó cada una.

Es PURO: sin red, sin BD y sin reloj. El adapter (`adapters/edgar.py`) se ocupa
de bajar los `companyfacts` y de elegir los datapoints anuales; aquí ya llegan
elegidos. Esa separación es la que permite testear el mapeo entero con hechos
sintéticos y, más adelante, con fixtures reales sin tocar la SEC.

## Orden de resolución (importa)

1. **Mapeo** — candidatos `us-gaap`, combinación de etiquetas, namespace `dei`.
2. **Líneas netas** — desagregar lo que el emisor publica junto.
3. **Ceros por ausencia** — la lista blanca de `concept_map`.
4. **Derivaciones** — identidades contables sobre lo ya resuelto.

Los ceros van ANTES que las derivaciones porque una derivación puede necesitar
un cero legítimo: en una empresa sin deuda, `interest_expense` no se publica, y
sin imputarlo a cero el EBIT derivado saldría hueco por falta de un sumando que
vale cero de verdad.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
from typing import Any

from app.modules.investment.enums import AccountingStd
from app.modules.investment.fundamentals.adapters.concept_map import (
    COMBINED_MAP,
    CONCEPT_MAP,
    CONDITIONAL_ZERO_ITEMS,
    DEI,
    DEI_MAP,
    IMPUTABLE_ZERO_ITEMS,
    NET_LINE_FALLBACKS,
    SIGN_FLIP,
    US_GAAP,
    qualify,
)
from app.modules.investment.fundamentals.canonical import (
    CANONICAL_ITEMS,
    CanonicalStatement,
    Provenance,
)
from app.modules.investment.fundamentals.validation import validate_statement

_ZERO = Decimal(0)


@dataclass(frozen=True)
class RawFiling:
    """Los hechos de un ejercicio, tal y como los deja el adapter.

    `facts` viene con el namespace por delante (`'us-gaap:Assets'`,
    `'dei:EntityCommonStockSharesOutstanding'`) y en unidades ABSOLUTAS de la
    divisa: la escala XBRL se aplica una sola vez, en el adapter, y a partir de
    aquí nadie vuelve a multiplicar por mil.
    """

    fiscal_year: int
    fiscal_year_end: date
    facts: Mapping[str, Decimal]
    filing_accession: str = ""
    currency: str = "USD"
    accounting_std: AccountingStd = AccountingStd.GAAP


@dataclass
class _Working:
    """Estado mutable de la normalización. Se congela al final en el canónico."""

    values: dict[str, Decimal | None] = field(
        default_factory=lambda: {item: None for item in CANONICAL_ITEMS}
    )
    provenance: dict[str, Provenance] = field(default_factory=dict)
    mapping: dict[str, Any] = field(default_factory=dict)

    def put(
        self,
        item: str,
        value: Decimal,
        provenance: Provenance,
        trace: dict[str, Any],
    ) -> None:
        self.values[item] = value
        if provenance is not Provenance.SOURCED:
            self.provenance[item] = provenance
        self.mapping[item] = {"provenance": str(provenance), **trace}

    def is_hole(self, item: str) -> bool:
        return self.values[item] is None


# ── 1. Mapeo ──────────────────────────────────────────────────────────


def _resolve_direct(facts: Mapping[str, Decimal], item: str) -> tuple[str, Decimal] | None:
    """Primer candidato `us-gaap` con dato. El orden de la lista es la prioridad."""
    for tag in CONCEPT_MAP.get(item, ()):
        value = facts.get(qualify(US_GAAP, tag))
        if value is None:
            continue
        return qualify(US_GAAP, tag), -value if tag in SIGN_FLIP else value
    return None


def _resolve_combined(facts: Mapping[str, Decimal], item: str) -> tuple[list[str], Decimal] | None:
    """Suma de un grupo de etiquetas menos otro. Basta con que exista UNA.

    Que baste una es deliberado: una empresa que solo amortizó deuda ese año
    publica `RepaymentsOf…` y nada de `ProceedsFrom…`, y su variación neta de
    deuda es exactamente ese importe en negativo. Exigir el grupo completo
    dejaría hueca una partida perfectamente conocida.
    """
    spec = COMBINED_MAP.get(item)
    if spec is None:
        return None
    total = _ZERO
    used: list[str] = []
    for sign, tags in ((1, spec.add), (-1, spec.sub)):
        for tag in tags:
            value = facts.get(qualify(US_GAAP, tag))
            if value is None:
                continue
            total += sign * value
            used.append(f"{'+' if sign > 0 else '-'}{qualify(US_GAAP, tag)}")
    if not used:
        return None
    return used, total


def _resolve_dei(facts: Mapping[str, Decimal], item: str) -> tuple[str, Decimal] | None:
    """Partidas de la portada del filing (namespace `dei`)."""
    for tag in DEI_MAP.get(item, ()):
        value = facts.get(qualify(DEI, tag))
        if value is None:
            continue
        return qualify(DEI, tag), value
    return None


def _map_items(raw: RawFiling, work: _Working) -> None:
    for item in CANONICAL_ITEMS:
        direct = _resolve_direct(raw.facts, item)
        if direct is not None:
            tag, value = direct
            work.put(item, value, Provenance.SOURCED, {"concepts": [tag]})
            continue

        combined = _resolve_combined(raw.facts, item)
        if combined is not None:
            tags, value = combined
            spec = COMBINED_MAP[item]
            work.put(item, value, spec.provenance, {"concepts": tags, "note": spec.note})
            continue

        dei = _resolve_dei(raw.facts, item)
        if dei is not None:
            tag, value = dei
            work.put(item, value, Provenance.SOURCED, {"concepts": [tag]})


# ── 2. Líneas netas ───────────────────────────────────────────────────


def _apply_net_lines(raw: RawFiling, work: _Working) -> list[str]:
    """Desagrega las líneas que el emisor publica netas. Devuelve los avisos.

    Solo actúa si la partida destino quedó hueca: las etiquetas partidas SIEMPRE
    ganan a la neta. Si actúa, la partida gemela se fija a cero para no doblar el
    ajuste, y el aviso deja constancia de que el desglose no era auditable.
    """
    notes: list[str] = []
    for spec in NET_LINE_FALLBACKS:
        if not work.is_hole(spec.into):
            continue
        value = raw.facts.get(qualify(US_GAAP, spec.concept))
        if value is None:
            continue
        tag = qualify(US_GAAP, spec.concept)
        work.put(spec.into, value, Provenance.DERIVED, {"concepts": [tag], "note": spec.reason})
        work.put(
            spec.zeroed,
            _ZERO,
            Provenance.IMPUTED_ZERO,
            {"concepts": [tag], "note": f"absorbida en '{spec.into}': {spec.reason}"},
        )
        notes.append(spec.reason)
    return notes


# ── 3. Ceros por ausencia ─────────────────────────────────────────────


def _impute_zeros(work: _Working) -> None:
    """Cero para las ausencias que la lista blanca permite leer como cero (§4.5)."""
    for item in CANONICAL_ITEMS:
        if not work.is_hole(item):
            continue
        if item in IMPUTABLE_ZERO_ITEMS:
            work.put(
                item,
                _ZERO,
                Provenance.IMPUTED_ZERO,
                {"note": "el filing no publica el concepto; en XBRL eso significa cero"},
            )
            continue

        conditions = CONDITIONAL_ZERO_ITEMS.get(item)
        if conditions is None:
            continue
        values = [work.values[condition] for condition in conditions]
        if any(value is None for value in values):
            continue
        if sum((value for value in values if value is not None), _ZERO) != _ZERO:
            continue
        work.put(
            item,
            _ZERO,
            Provenance.IMPUTED_ZERO,
            {
                "note": (
                    f"ausente y sin deuda viva ({', '.join(conditions)} a cero), "
                    "así que el cero es real"
                )
            },
        )


# ── 4. Derivaciones ───────────────────────────────────────────────────


@dataclass(frozen=True)
class _Derivation:
    rule: str
    compute: Callable[[dict[str, Decimal | None]], Decimal | None]
    note: str


def _derive_ebit(values: dict[str, Decimal | None]) -> Decimal | None:
    """`pretax_income + interest_expense`.

    `OperatingIncomeLoss` no es fiable en XBRL: JNJ dejó de publicarlo en 2015 y
    los REIT no tienen línea de resultado operativo. Se prefiere el pretax
    REPORTADO (partida 49) y solo si falta se reconstruye como
    `net_income + taxes`, que ignora minoritarios y actividades discontinuadas.
    """
    interest = values.get("interest_expense")
    if interest is None:
        return None
    pretax = values.get("pretax_income")
    if pretax is None:
        net_income, taxes = values.get("net_income"), values.get("taxes")
        if net_income is None or taxes is None:
            return None
        pretax = net_income + taxes
    return pretax + interest


def _derive_total_liabilities(values: dict[str, Decimal | None]) -> Decimal | None:
    """`total_assets − equity`, la identidad del balance.

    MCD no publica `Liabilities` (sí `LiabilitiesAndStockholdersEquity`, que es
    el activo con otro nombre). Su patrimonio es NEGATIVO por recompras y el
    engine ya trata ese caso con guardas, así que la resta sigue valiendo.
    """
    total_assets, equity = values.get("total_assets"), values.get("equity")
    if total_assets is None or equity is None:
        return None
    return total_assets - equity


DERIVATIONS: Mapping[str, _Derivation] = {
    "ebit": _Derivation(
        rule="pretax_income + interest_expense",
        compute=_derive_ebit,
        note=(
            "El resultado operativo no venía en el filing. Al derivarlo así, "
            "`ebit − intereses` es idénticamente el resultado antes de impuestos, por lo "
            "que el engine deja de evaluar la bandera `ebt_divergence` para este "
            "ejercicio en vez de darla por superada."
        ),
    ),
    "total_liabilities": _Derivation(
        rule="total_assets - equity",
        compute=_derive_total_liabilities,
        note=(
            "El pasivo total no venía en el filing. Al derivarlo así, el cuadre del "
            "balance se cumple por construcción y deja de ser verificable."
        ),
    ),
}
"""Identidades contables que rellenan una partida ausente.

Se aplican SOLO sobre huecos y marcan `derived`: aplican una igualdad exacta, no
inventan un dato. Ambas tienen un efecto colateral que hay que declarar —
inutilizan la comprobación que tendría esa partida como testigo—, y por eso el
`note` viaja hasta `raw_source_ref`: quien audite el ejercicio ve por qué esa
comprobación no aparece."""


def _apply_derivations(work: _Working) -> None:
    for item, derivation in DERIVATIONS.items():
        if not work.is_hole(item):
            continue
        value = derivation.compute(work.values)
        if value is None:
            continue
        work.put(
            item,
            value,
            Provenance.DERIVED,
            {"rule": derivation.rule, "note": derivation.note},
        )


# ── Escala de las acciones ────────────────────────────────────────────

#: Partidas de recuento de acciones. Comparten escala: si una está en millones,
#: todas lo están, porque salen del mismo estado de resultados.
_SHARE_ITEMS = ("shares_basic", "shares_diluted")

#: Desfase mínimo para considerarlo un cambio de escala y no ruido contable.
#: Mil, no diez: un emisor puede presentar en miles, millones o billones, pero
#: nunca en "decenas". Un desfase de 2× es otra cosa y no se toca.
_MIN_SCALE_EXPONENT = 3

#: Cuánto puede alejarse el cociente de la potencia de 10 exacta. Las acciones
#: medias del ejercicio y las del cierre difieren por las recompras del año —en
#: MCD, un 0,4%—, así que el cociente ronda 10^k pero no lo clava.
_SCALE_TOLERANCE = Decimal("0.20")


def detect_scale_exponent(value: Decimal, reference: Decimal) -> int | None:
    """Exponente de 10 que separa dos magnitudes que deberían ser comparables.

    `None` cuando el desfase no es una potencia de 10 limpia: eso ya no es un
    problema de escala sino de otra cosa, y corregirlo a ojo sería inventar.
    Sólo se afirma lo que el testigo demuestra.
    """
    if value == _ZERO or reference == _ZERO:
        return None
    ratio = abs(reference) / abs(value)
    if ratio <= _ZERO:
        return None
    exponent = int(ratio.log10().to_integral_value())
    if abs(exponent) < _MIN_SCALE_EXPONENT:
        return None
    expected = Decimal(10) ** exponent
    if abs(ratio - expected) / expected > _SCALE_TOLERANCE:
        return None
    return exponent


def _rescale_shares(raw: RawFiling, work: _Working) -> dict[str, Any] | None:
    """Corrige el recuento de acciones cuando el emisor lo presenta en millones.

    **Por qué hace falta.** El XBRL declara la unidad `shares` tanto si el valor
    va en unidades como si va en millones: nada en el fichero distingue
    `746300000` de `746.3`. McDonald's cambió de una a otra en su 10-K de 2023 y
    reexpresó los ejercicios anteriores, así que la política `is_latest_view`
    —quedarse con la revisión más reciente, que es lo correcto— importó toda la
    serie en millones mientras el dinero seguía en unidades. Resultado: la caja
    libre por acción salía 9.515.610 $ en vez de 9,52 $.

    **El testigo es `shares_outstanding_eop`**, las acciones en circulación al
    cierre. Viene del namespace `dei` (la portada del filing), que siempre las
    publica en unidades reales, y es la MISMA magnitud que las medias del
    ejercicio: difieren por las recompras del año, jamás por un factor de mil.

    El BPA reportado sería un testigo más exacto —`resultado/acciones = BPA` es
    una identidad— pero **no llega hasta aquí**: `annual._is_per_share` descarta
    los ratios por acción a propósito, para que un `EarningsPerShareBasic` no se
    cuele como si fuera un importe. Comprobado ejecutando el pipeline, no
    deducido: en los 205 hechos de MCD 2021 el EPS no aparece.

    Si el desfase no es una potencia de 10 limpia no se toca nada, y si falta el
    testigo tampoco — pero entonces el cuadre de `validation.py` deja la bandera
    para que no pase inadvertido.
    """
    shares_basic = work.values.get("shares_basic")
    reference = work.values.get("shares_outstanding_eop")
    if shares_basic is None or reference is None:
        return None

    exponent = detect_scale_exponent(shares_basic, reference)
    if exponent is None or exponent <= 0:
        return None

    factor = Decimal(10) ** exponent
    corrected: dict[str, str] = {}
    for item in _SHARE_ITEMS:
        current = work.values.get(item)
        if current is None:
            continue
        work.values[item] = current * factor
        corrected[item] = f"{current} -> {current * factor}"

    if not corrected:
        return None
    return {
        "rule": "shares_scale",
        "factor": str(factor),
        "witness": "shares_outstanding_eop",
        "witness_value": str(reference),
        "corrected": corrected,
        "note": (
            f"El emisor presenta las acciones medias en unidades de {factor}. Detectado "
            f"porque no eran del mismo orden que las acciones en circulación al cierre "
            f"({reference}), que el namespace dei publica siempre en unidades."
        ),
    }


# ── Entrada pública ───────────────────────────────────────────────────


def normalize(raw: RawFiling) -> CanonicalStatement:
    """Estado canónico de un ejercicio, con procedencia y traza del mapeo.

    Los cuadres de `validation.py` se ejecutan al final y sus avisos viajan en
    `raw_source_ref['quality_flags']`: un cuadre roto NO aborta la ingesta, marca
    el ejercicio como sospechoso.
    """
    work = _Working()
    _map_items(raw, work)
    net_line_notes = _apply_net_lines(raw, work)
    _impute_zeros(work)
    # La escala se arregla ANTES de derivar: hay derivaciones que dividen entre
    # acciones, y corregirlas después dejaría el valor derivado con la escala
    # vieja mientras la partida de origen ya estaría bien.
    scale_fix = _rescale_shares(raw, work)
    _apply_derivations(work)

    source_ref: dict[str, Any] = {
        "accession": raw.filing_accession,
        "mapping": work.mapping,
        "notes": net_line_notes,
    }
    if scale_fix is not None:
        source_ref["scale_corrections"] = [scale_fix]
    statement = CanonicalStatement(
        fiscal_year=raw.fiscal_year,
        fiscal_year_end=raw.fiscal_year_end,
        accounting_std=raw.accounting_std,
        currency=raw.currency,
        filing_accession=raw.filing_accession,
        item_provenance=dict(work.provenance),
        raw_source_ref=source_ref,
        **{item: work.values[item] for item in CANONICAL_ITEMS},  # type: ignore[arg-type]
    )

    # Los cuadres necesitan el estado ya montado (miran procedencias), así que se
    # rehace con sus avisos dentro en vez de mutar un dataclass congelado.
    quality_flags = validate_statement(statement)
    return replace(
        statement,
        raw_source_ref={
            **source_ref,
            "quality_flags": [flag.as_dict() for flag in quality_flags],
        },
    )


def mapped_items(statement: CanonicalStatement) -> dict[str, list[str]]:
    """Partida canónica → conceptos XBRL que la alimentaron.

    Atajo de auditoría sobre `raw_source_ref`: responde "¿de dónde salió este
    número?" sin que quien pregunta tenga que conocer la forma del JSON.
    """
    mapping: dict[str, Any] = statement.raw_source_ref.get("mapping", {})
    return {item: list(trace["concepts"]) for item, trace in mapping.items() if "concepts" in trace}
