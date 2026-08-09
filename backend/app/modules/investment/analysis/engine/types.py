"""Tipos del engine (PHASE-44.2, ARCHITECTURE §4.1).

Todo inmutable (`frozen=True`): el engine no muta sus inputs ni sus salidas.

El tipo central es `MetricResult`. Su contrato es el corazón del módulo: una
métrica **nunca desaparece y nunca miente**. Si no se puede calcular, sale con
`status="not_computable"` y una `reason` en español; si se calculó con un
denominador aproximado, sale con `status="approximation"`; y si la pregunta que
hace no se plantea en este caso, con `status="not_applicable"` y su motivo — que
no es lo mismo y por eso son dos estados. Jamás un 0 implícito, jamás una
excepción, jamás una clave ausente (§4.5) — el frontend enseña el porqué, que es
más informativo que un hueco.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, ClassVar, Literal

from app.modules.investment.enums import AccountingStd, SectorInternal, ThresholdDirection
from app.modules.investment.fundamentals.canonical import (
    CanonicalStatement,
    Provenance,
    combine_provenance,
)

MetricStatus = Literal["ok", "not_computable", "approximation", "not_applicable"]
"""`approximation` = calculada, pero con un input degradado (típicamente el
primer año de la serie, sin t−1 para la media de balance) [Dec.3].

`not_applicable` (PHASE-44.17) = **la pregunta que hace la métrica no se plantea
en este caso**, que no es lo mismo que no haber podido responderla. El caso que
lo trajo: el muro de vencimientos (L4) de una empresa sin deuda venciendo a doce
meses salía «denominador cero», indistinguible de un dato que falta — cuando es
el mejor resultado posible de esa métrica. Un `not_applicable` puede llevar
banda; un `not_computable` nunca, porque no se ha comprobado nada."""

Band = Literal["healthy", "caution", "stressed"]
Severity = Literal["info", "amber", "red"]


# ── Entrada ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SecuritySnapshot:
    """Los atributos del valor que gobiernan QUÉ se calcula.

    `is_financial` desactiva los modelos forenses (Beneish/Altman no aplican a
    bancos) y `is_reit` activa la variante FFO en la capa 3. `sector` y
    `accounting_std` seleccionan el juego de umbrales [Dec.8].
    """

    ticker: str
    sector: SectorInternal
    accounting_std: AccountingStd
    is_financial: bool = False
    is_reit: bool = False


@dataclass(frozen=True)
class StatementSeries:
    """La serie anual de una empresa, en orden ascendente por año fiscal.

    Solo debe contener la vista vigente de cada año (`is_latest_view`): mezclar
    dos filings del mismo año haría que la serie tuviera dos verdades. La
    detección de reexpresiones vive en `restatements.py`, no aquí.
    """

    security: SecuritySnapshot
    statements: tuple[CanonicalStatement, ...]
    as_of: date

    def __post_init__(self) -> None:
        years = [s.fiscal_year for s in self.statements]
        if len(set(years)) != len(years):
            raise ValueError(f"La serie tiene años fiscales duplicados: {years}")
        if years != sorted(years):
            raise ValueError(f"La serie debe venir en orden ascendente por año: {years}")

    @property
    def years(self) -> tuple[int, ...]:
        return tuple(s.fiscal_year for s in self.statements)

    @property
    def latest(self) -> CanonicalStatement | None:
        return self.statements[-1] if self.statements else None

    def by_year(self, fiscal_year: int) -> CanonicalStatement | None:
        for statement in self.statements:
            if statement.fiscal_year == fiscal_year:
                return statement
        return None

    def prior(self, fiscal_year: int) -> CanonicalStatement | None:
        """El ejercicio inmediatamente anterior EN LA SERIE.

        Devuelve `None` si no está: puede ser el primer año disponible o un
        hueco en medio. En ambos casos no hay t−1 utilizable, y quien pida una
        media de balance obtendrá `approximation` [Dec.3] — nunca un salto
        silencioso a un año más lejano, que falsearía la media.
        """
        previous: CanonicalStatement | None = None
        for statement in self.statements:
            if statement.fiscal_year == fiscal_year:
                if previous is not None and previous.fiscal_year == fiscal_year - 1:
                    return previous
                return None
            previous = statement
        return None


# ── Importes intermedios ──────────────────────────────────────────────


@dataclass(frozen=True)
class Amount:
    """Un importe en tránsito por el engine, con su estado y procedencia.

    Existe para que un hueco (`value=None`) viaje con el NOMBRE de lo que falta
    (`missing`) desde la partida hasta el `MetricResult` final. Sin esto, la
    razón de un `not_computable` sería "falta algún input", que no es
    accionable; con esto es "falta la partida 'inventory'".
    """

    value: Decimal | None
    provenance: Provenance = Provenance.SOURCED
    status: MetricStatus = "ok"
    missing: str | None = None
    reason: str | None = None

    @property
    def is_missing(self) -> bool:
        return self.value is None

    @staticmethod
    def absent(missing: str, reason: str | None = None) -> Amount:
        return Amount(
            value=None,
            status="not_computable",
            missing=missing,
            reason=reason or f"falta la partida '{missing}'",
        )


def combine_amounts(*amounts: Amount) -> tuple[Provenance, MetricStatus, str | None]:
    """Procedencia, estado y razón resultantes de combinar varios importes.

    - Procedencia: la más degradada [canonical.combine_provenance].
    - Estado: `not_computable` si falta alguno; si no, `approximation` si alguno
      lo es; si no, `ok`. La degradación nunca se pierde por el camino.
    """
    provenance = combine_provenance(*(a.provenance for a in amounts))
    missing = [a for a in amounts if a.is_missing]
    if missing:
        reasons = [a.reason or f"falta '{a.missing}'" for a in missing if a.reason or a.missing]
        return provenance, "not_computable", "; ".join(dict.fromkeys(reasons)) or "input ausente"
    approximated = [a for a in amounts if a.status == "approximation"]
    if approximated:
        reasons = [a.reason for a in approximated if a.reason]
        return provenance, "approximation", "; ".join(dict.fromkeys(reasons)) or None
    return provenance, "ok", None


# ── Umbrales ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ThresholdSpec:
    """Umbral de una métrica: `direction` + 4 cortes → banda [Dec.8].

    Codificación por dirección (los cortes que no aplican van a `None`):
    - `higher_better` (p.ej. L1 ">1,5 · 1,0-1,5 · <1,0"): `low_alarm=1,0`,
      `low_ok=1,5`. value < low_alarm → stressed; < low_ok → caution; resto
      healthy.
    - `lower_better` (p.ej. S1 "<0,6 · 0,6-0,75 · >0,75"): `high_ok=0,6`,
      `high_alarm=0,75`. value > high_alarm → stressed; > high_ok → caution;
      resto healthy.
    - `band` (banda central): fuera de [low_alarm, high_alarm] → stressed;
      dentro de [low_ok, high_ok] → healthy; resto caution.
    """

    metric_key: str
    direction: ThresholdDirection
    low_alarm: Decimal | None = None
    low_ok: Decimal | None = None
    high_ok: Decimal | None = None
    high_alarm: Decimal | None = None
    model_variant: str | None = None
    applies: bool = True
    not_applicable_reason: str | None = None
    """Por qué la vara no aplica a este (sector × norma), en español
    (PHASE-44.21). Viaja al run y de ahí a la pantalla: un número gris sin
    explicación se lee como «no se ha podido calcular», que es otra cosa."""

    def __post_init__(self) -> None:
        if not self.applies and not self.not_applicable_reason:
            raise ValueError(
                f"{self.metric_key}: un umbral que no aplica DEBE decir por qué — "
                "un «N/A» mudo es indistinguible de un fallo de cálculo"
            )

    def band_for(self, value: Decimal | None) -> Band | None:
        """Banda de un valor. `None` cuando no hay banda que aplicar — que NO
        es lo mismo que 'sano': métricas como el DSO (A1) no tienen banda
        absoluta, solo se evalúa su deriva en la capa 1.5."""
        if value is None or not self.applies:
            return None
        if self.direction is ThresholdDirection.HIGHER_BETTER:
            if self.low_alarm is not None and value < self.low_alarm:
                return "stressed"
            if self.low_ok is not None and value < self.low_ok:
                return "caution"
            return "healthy" if (self.low_alarm, self.low_ok) != (None, None) else None
        if self.direction is ThresholdDirection.LOWER_BETTER:
            if self.high_alarm is not None and value > self.high_alarm:
                return "stressed"
            if self.high_ok is not None and value > self.high_ok:
                return "caution"
            return "healthy" if (self.high_ok, self.high_alarm) != (None, None) else None
        # BAND — banda central
        if (self.low_alarm is not None and value < self.low_alarm) or (
            self.high_alarm is not None and value > self.high_alarm
        ):
            return "stressed"
        within_low = self.low_ok is None or value >= self.low_ok
        within_high = self.high_ok is None or value <= self.high_ok
        return "healthy" if within_low and within_high else "caution"


# ── Salida ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MetricResult:
    """El resultado de UNA métrica en UN año fiscal.

    `value` es `None` si y solo si la métrica no trae número, y eso ocurre por
    dos motivos que NO se pueden confundir (§4.5):

    - `not_computable` — se intentó y no se pudo (falta una partida, denominador
      cero…). Nunca lleva banda: no se ha comprobado nada.
    - `not_applicable` — la métrica no tiene aplicación en este caso, y eso es
      información. Puede llevar banda cuando la ausencia ES el resultado (L4 sin
      deuda a doce meses).

    En los dos, `reason` explica por qué en español.
    """

    key: str
    fiscal_year: int
    value: Decimal | None
    status: MetricStatus
    provenance: Provenance
    reason: str | None = None
    band: Band | None = None

    #: Los dos estados sin número. Se enumeran una vez para que el invariante y
    #: quien lea el contrato vean lo mismo.
    VALUELESS: ClassVar[frozenset[str]] = frozenset({"not_computable", "not_applicable"})

    def __post_init__(self) -> None:
        if (self.value is None) != (self.status in self.VALUELESS):
            raise ValueError(
                f"{self.key}: value={self.value!r} incoherente con status={self.status!r} — "
                "un valor ausente DEBE ser not_computable o not_applicable, y viceversa"
            )
        if self.status in self.VALUELESS and not self.reason:
            raise ValueError(f"{self.key}: {self.status} exige una razón (§4.5)")
        if self.status == "not_computable" and self.band is not None:
            raise ValueError(
                f"{self.key}: not_computable con banda {self.band!r} — una métrica que no se "
                "ha podido calcular no puede tener semáforo"
            )


@dataclass(frozen=True)
class Flag:
    """Señal cualitativa dirigida al usuario, en lenguaje de negocio."""

    key: str
    severity: Severity
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)


FlagOutcome = Literal["fired", "clear", "not_computable", "not_applicable"]
"""Los cuatro desenlaces de una regla de bandera.

`not_applicable` (PHASE-44.21) es «la regla no se plantea en este sector» —el
inventario de una eléctrica— y no «no se pudo comprobar»: lo segundo invita a
ingerir más datos, y aquí no hay nada que ingerir."""


@dataclass(frozen=True)
class FlagEvaluation:
    """Qué le pasó a una REGLA de bandera, haya saltado o no (PHASE-44.17).

    Una `Flag` sólo existe cuando salta. Eso deja sin representar los otros dos
    desenlaces, que la síntesis colapsaba en uno: preguntaba «¿hay bandera con
    esta clave?» y traducía el no a **«no se ha encendido»** — que se lee como
    *comprobado y limpio*. Pero una regla que aborta porque le falta un dato
    (sin coste de ventas, C3 no llega a ejecutarse nunca) también responde que
    no, y ahí no se ha comprobado nada.

    Una evaluación POR REGLA y por serie, no por año: las reglas exigen rachas
    («dos años seguidos»), así que la unidad de decisión es la serie entera.

    `years_evaluated` y `years_unevaluable` viajan para que la razón se pueda
    auditar sin recomputar: son los ejercicios en los que la regla pudo mirar y
    los que se saltó.
    """

    key: str
    outcome: FlagOutcome
    reason: str | None = None
    years_evaluated: tuple[int, ...] = ()
    years_unevaluable: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if self.outcome == "not_computable" and not self.reason:
            raise ValueError(f"{self.key}: una regla que no se pudo evaluar DEBE decir por qué")


@dataclass(frozen=True)
class Verdict:
    """Síntesis final (Capa 4). Se rellena en la fase de `synthesis`; aquí solo
    queda declarado el tipo para que el contrato del engine esté completo."""

    label: str
    confidence: Decimal
    flags: tuple[Flag, ...] = ()
    notes: tuple[str, ...] = ()
