"""Hechos XBRL → ejercicios anuales (PHASE-44.6, ARCHITECTURE §3.2).

PURO: sin red, sin BD, sin reloj. Entra la lista plana de hechos que devuelve el
adapter y salen los `RawFiling` que consume `normalization.py`, uno por ejercicio.

## Por qué esto no lo hace la librería

`edgartools` expone `get_annual_fact(concept, fiscal_year=N)`, que parece
exactamente esto y no lo es. Su `fiscal_year` sale del campo `fy` de
`companyfacts`, que NO es el ejercicio del dato sino el del INFORME que lo
contiene: en el 10-K de 2024 las tres columnas comparativas (2024, 2023, 2022)
viajan las tres con `fy=2024` y `fp=FY`. Pedir el ejercicio 2023 devuelve
entonces la cifra ORIGINAL de 2023 —la del informe de 2023— y nunca la
reexpresada, que es justo la que el análisis quiere ver.

El cruzado con MCD, Realty Income y JNJ validó otro anclaje, y es el que se
implementa aquí: **la fecha de cierre manda** (`period_end`), no la etiqueta del
informe.

## Las reglas

1. Solo `10-K` con `fp=FY`. Los trimestres y los YTD parciales fuera.
2. Un flujo (resultados, caja) es anual si dura entre 350 y 380 días. El rango es
   ancho a propósito: los años fiscales de 52/53 semanas no duran 365 (JNJ cierra
   el 28 de diciembre, 363 días) y un rango estrecho los dejaría fuera.
3. Un saldo (balance) es del ejercicio si su instante ES la fecha de cierre.
4. Cuando varios filings reportan el mismo ejercicio, gana el MÁS RECIENTE: esa
   es la vista vigente, con las reexpresiones ya aplicadas.
5. Los hechos de la taxonomía `dei` viven en la portada y su fecha es POSTERIOR
   al cierre, así que no se pueden anclar por fecha: se atribuyen por
   `accession`, al ejercicio del que ese 10-K es informe principal.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import date

from app.modules.investment.enums import AccountingStd
from app.modules.investment.fundamentals.adapters.base import FilingRef, XbrlFact
from app.modules.investment.fundamentals.adapters.concept_map import DEI
from app.modules.investment.fundamentals.normalization import RawFiling

ANNUAL_FORMS: frozenset[str] = frozenset({"10-K"})
"""Solo el 10-K original.

Las enmiendas (`10-K/A`) quedan fuera a propósito: suelen reexpresar una parte
del informe y mezclarlas exigiría saber qué partidas toca cada una. La vía por la
que una reexpresión SÍ entra es la comparativa del 10-K siguiente, que es
completa y viene con su fecha de presentación — y ahí la regla 4 la recoge sola."""

MIN_ANNUAL_DAYS = 350
MAX_ANNUAL_DAYS = 380


def _is_per_share(unit: str) -> bool:
    """¿La unidad es un 'por acción' (`USD/shares`, `USD per share`…)?

    Se detecta por forma y no con una lista cerrada de literales: la SEC escribe
    `USD/shares` y `edgartools` lo reetiqueta como `USD per share`, así que una
    lista fija se queda obsoleta en cuanto cambia cualquiera de los dos.

    Importa porque los ratios por acción no son partidas canónicas: un
    `EarningsPerShareBasic` colado como importe daría un 'beneficio' de 11,39
    dólares para una empresa que ganó 8.223 millones.
    """
    normalized = unit.lower()
    return "/" in normalized or " per " in normalized


def _is_annual(fact: XbrlFact) -> bool:
    if fact.form_type not in ANNUAL_FORMS or fact.fiscal_period != "FY":
        return False
    if _is_per_share(fact.unit):
        return False
    if fact.is_instant:
        return True
    days = fact.duration_days
    return days is not None and MIN_ANNUAL_DAYS <= days <= MAX_ANNUAL_DAYS


def _own_filings(facts: Sequence[XbrlFact]) -> dict[str, FilingRef]:
    """Accession → el ejercicio del que ese filing es informe PRINCIPAL.

    Un 10-K reporta un ejercicio y arrastra dos o tres comparativos. El principal
    es el de cierre más reciente entre sus propios hechos, y su etiqueta (`fy`)
    es de fiar precisamente ahí: describe el informe, que es lo que estamos
    identificando.

    El cierre se decide con los FLUJOS (resultados, caja), nunca con los saldos:
    un periodo anual no puede terminar después del cierre del ejercicio, mientras
    que un saldo sí —un 10-K puede traer un hecho posterior al cierre, como la
    deuda emitida en enero—. Tomar el saldo más reciente daría un ejercicio
    fantasma con fecha de enero al que no se anclaría ninguna otra partida, y de
    paso se perdería el ejercicio de verdad.
    """
    by_accession: dict[str, list[XbrlFact]] = defaultdict(list)
    for fact in facts:
        by_accession[fact.accession].append(fact)

    refs: dict[str, FilingRef] = {}
    for accession, group in by_accession.items():
        anchored = [fact for fact in group if fact.taxonomy != DEI]
        if not anchored:
            continue
        flows = [fact for fact in anchored if not fact.is_instant]
        primary = max(flows or anchored, key=lambda fact: fact.period_end)
        refs[accession] = FilingRef(
            accession=accession,
            filing_date=primary.filing_date,
            fiscal_year=primary.fiscal_year,
            fiscal_year_end=primary.period_end,
            form_type=primary.form_type,
        )
    return refs


def filing_refs(facts: Iterable[XbrlFact]) -> tuple[FilingRef, ...]:
    """Los 10-K que hay en los hechos, del más reciente al más antiguo."""
    annual = [fact for fact in facts if _is_annual(fact)]
    refs = _own_filings(annual).values()
    return tuple(sorted(refs, key=lambda ref: ref.fiscal_year_end, reverse=True))


def _pick_latest(candidates: list[XbrlFact]) -> XbrlFact:
    """La vista vigente de un dato: la del filing más reciente.

    Empate de fecha de presentación (un 10-K y su enmienda el mismo día, o dos
    unidades para el mismo concepto): decide el accession para que el resultado
    sea determinista y no dependa del orden de la lista.
    """
    return max(candidates, key=lambda fact: (fact.filing_date, fact.accession))


def build_raw_filings(
    facts: Iterable[XbrlFact],
    *,
    limit: int | None = None,
    accounting_std: AccountingStd = AccountingStd.GAAP,
) -> tuple[RawFiling, ...]:
    """Un `RawFiling` por ejercicio, del más antiguo al más reciente.

    `limit` recorta a los N ejercicios MÁS RECIENTES antes de devolver — el orden
    ascendente es el que exige `StatementSeries`, pero recortar por el principio
    tiraría los años que interesan.

    Solo se emiten los ejercicios que tienen 10-K propio. Un año que solo aparece
    como comparativo de un informe posterior se queda fuera: no tiene portada de
    la que sacar las acciones en circulación ni `accession` propio con el que
    auditar, y su serie sería sistemáticamente más pobre que la de los demás.
    """
    annual = [fact for fact in facts if _is_annual(fact)]
    own = _own_filings(annual)

    # Si dos filings declararan el mismo cierre como principal, manda el
    # presentado después. Fijar el criterio evita que el ejercicio dependa del
    # orden en que llegaron los hechos.
    periods: dict[date, FilingRef] = {}
    for ref in own.values():
        current = periods.get(ref.fiscal_year_end)
        if current is None or (ref.filing_date, ref.accession) > (
            current.filing_date,
            current.accession,
        ):
            periods[ref.fiscal_year_end] = ref

    by_period: dict[date, dict[str, list[XbrlFact]]] = defaultdict(lambda: defaultdict(list))
    for fact in annual:
        if fact.taxonomy == DEI:
            # La portada no se ancla por fecha: pertenece al ejercicio del que su
            # filing es informe principal.
            own_ref = own.get(fact.accession)
            if own_ref is not None:
                by_period[own_ref.fiscal_year_end][fact.key].append(fact)
            continue
        if fact.period_end in periods:
            by_period[fact.period_end][fact.key].append(fact)

    filings: list[RawFiling] = []
    for fiscal_year_end in sorted(periods):
        ref = periods[fiscal_year_end]
        resolved = {key: _pick_latest(group) for key, group in by_period[fiscal_year_end].items()}
        filings.append(
            RawFiling(
                fiscal_year=ref.fiscal_year,
                fiscal_year_end=fiscal_year_end,
                facts={key: fact.value for key, fact in resolved.items()},
                filing_accession=ref.accession,
                currency=_currency_of(resolved.values()),
                accounting_std=accounting_std,
            )
        )

    if limit is not None and limit > 0:
        filings = filings[-limit:]
    return tuple(filings)


def _currency_of(facts: Iterable[XbrlFact]) -> str:
    """La divisa de los importes del ejercicio.

    Se lee de las unidades en vez de fijar USD: un emisor extranjero que presenta
    ante la SEC puede reportar en su divisa, y un 'USD' por defecto convertiría
    una cifra en euros en una cifra en dólares sin que nadie se entere.
    """
    counts: dict[str, int] = defaultdict(int)
    for fact in facts:
        if len(fact.unit) == 3 and fact.unit.isalpha():
            counts[fact.unit.upper()] += 1
    if not counts:
        return "USD"
    return max(counts.items(), key=lambda item: (item[1], item[0]))[0]


def is_annual_fact(fact: XbrlFact) -> bool:
    """Público: ¿un hecho es un dato anual utilizable (10-K, fp=FY, no per-share,
    duración anual o instante)? Lo usa `restatements.py` para comparar filings."""
    return _is_annual(fact)


def restated_periods(facts: Iterable[XbrlFact]) -> dict[date, tuple[str, ...]]:
    """Ejercicios que más de un 10-K ha reportado, con sus accessions.

    No decide si hubo reexpresión —eso compara valores y lo hará
    `restatements.py`—, solo señala dónde MIRAR: un ejercicio con un único filing
    no puede haber sido reexpresado.
    """
    annual = [fact for fact in facts if _is_annual(fact) and fact.taxonomy != DEI]
    seen: dict[date, set[str]] = defaultdict(set)
    for fact in annual:
        seen[fact.period_end].add(fact.accession)
    return {
        period: tuple(sorted(accessions))
        for period, accessions in sorted(seen.items())
        if len(accessions) > 1
    }
