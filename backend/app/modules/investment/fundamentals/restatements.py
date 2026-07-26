"""Detección de reexpresiones entre filings (PHASE-44.7, ARCHITECTURE §3.4, Dec.6).

Cuando dos 10-K distintos reportan el MISMO ejercicio con cifras distintas, la
diferencia es una reexpresión — y una reexpresión es señal forense (el emisor
cambió una cifra ya publicada). `annual.restated_periods` dice DÓNDE mirar (qué
ejercicios reportó más de un filing); aquí se comparan los valores y se marca la
divergencia si supera el umbral.

PURO: sin BD ni reloj. Compara a nivel de CONCEPTO XBRL (`us-gaap:Revenues`),
no de partida canónica: es la cifra que el emisor realmente cambió, y así la
detección no depende del mapeo. El `detected_at` y la persistencia los pone el
servicio (que sí tiene reloj y BD).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.modules.investment.fundamentals.adapters.annual import (
    is_annual_fact,
    restated_periods,
)
from app.modules.investment.fundamentals.adapters.base import XbrlFact
from app.modules.investment.fundamentals.adapters.concept_map import DEI

DEFAULT_THRESHOLD = Decimal("0.01")
"""Divergencia relativa a partir de la cual se marca reexpresión (1%, Dec.6). Un
redondeo distinto NO es una reexpresión; el umbral relativo lo filtra."""


@dataclass(frozen=True)
class RestatementComparison:
    """Una reexpresión detectada: dos filings del mismo ejercicio con cifras
    distintas en al menos un concepto."""

    fiscal_year: int
    fiscal_year_end: date
    filing_a: str
    """El filing ORIGINAL (presentado antes)."""
    filing_b: str
    """El filing que REEXPRESA (presentado después)."""
    divergences: list[dict[str, str]]
    """[{concept, value_a, value_b, pct}] — todo string para JSONB exacto."""


def detect_restatements(
    facts: Iterable[XbrlFact], *, threshold: Decimal = DEFAULT_THRESHOLD
) -> list[RestatementComparison]:
    """Reexpresiones entre los filings presentes en `facts`.

    Para cada ejercicio reportado por más de un 10-K, compara el filing más
    antiguo (original) con el más reciente (reexpresado) concepto a concepto, y
    recoge los que difieren más del umbral relativo.
    """
    facts = list(facts)
    periods = restated_periods(facts)
    if not periods:
        return []

    # (period_end, accession) → {concepto: valor}; y accession → fecha de filing.
    # `fiscal_year` se toma del filing ORIGINAL: su etiqueta `fy` describe su
    # ejercicio principal (2023), mientras que el mismo periodo como comparativo
    # de un 10-K posterior viaja con el `fy` del INFORME (2024) — que no es su año.
    values: dict[tuple[date, str], dict[str, Decimal]] = defaultdict(dict)
    filing_date: dict[str, date] = {}
    fiscal_year: dict[tuple[date, str], int] = {}
    for fact in facts:
        if not is_annual_fact(fact) or fact.taxonomy == DEI:
            continue
        values[(fact.period_end, fact.accession)][fact.key] = fact.value
        filing_date[fact.accession] = fact.filing_date
        fiscal_year[(fact.period_end, fact.accession)] = fact.fiscal_year

    results: list[RestatementComparison] = []
    for period_end, accessions in periods.items():
        ordered = sorted(accessions, key=lambda acc: (filing_date.get(acc, date.min), acc))
        original, latest = ordered[0], ordered[-1]
        if original == latest:  # defensivo: restated_periods garantiza ≥2
            continue
        va = values[(period_end, original)]
        vb = values[(period_end, latest)]

        divergences: list[dict[str, str]] = []
        for concept in sorted(va.keys() & vb.keys()):
            a, b = va[concept], vb[concept]
            base = abs(a)
            if base == 0:  # sin base relativa fiable; un 0→algo no es reexpresión de magnitud
                continue
            pct = abs(b - a) / base
            if pct > threshold:
                divergences.append(
                    {
                        "concept": concept,
                        "value_a": str(a),
                        "value_b": str(b),
                        "pct": str(pct.quantize(Decimal("0.0001"))),
                    }
                )

        if divergences:
            results.append(
                RestatementComparison(
                    fiscal_year=fiscal_year.get((period_end, original), period_end.year),
                    fiscal_year_end=period_end,
                    filing_a=original,
                    filing_b=latest,
                    divergences=divergences,
                )
            )
    return results
