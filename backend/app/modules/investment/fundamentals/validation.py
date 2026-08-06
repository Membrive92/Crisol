"""Cuadres de un estado financiero ingerido (PHASE-44.6, ARCHITECTURE §3.3, Dec.18).

Comprueba identidades contables que TIENEN que cumplirse y, cuando no se
cumplen, emite una `QualityFlag`. **Nunca aborta la ingesta**: un cuadre roto
significa "este dato es sospechoso", no "descarta el ejercicio". El usuario
prefiere ver el año con una advertencia a no verlo.

Por qué `QualityFlag` y no la `Flag` del engine: son cosas distintas aunque se
parezcan. La `Flag` del engine habla del NEGOCIO ("el dividendo se paga con
deuda") y la lee el informe; esta habla del DATO ("el balance no cuadra") y vive
en `raw_source_ref`. Además, importar el engine desde la ingesta invertiría la
dependencia — el engine importa el canónico, no al revés.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

from app.modules.investment.fundamentals.canonical import CanonicalStatement, Provenance

Severity = Literal["info", "amber", "red"]

BALANCE_TOLERANCE = Decimal("0.01")
"""1% sobre el activo. No es holgura arbitraria: los filings redondean a millón
y las partidas 'otros' se reparten, así que exigir el céntimo daría falsos
positivos en empresas impecables."""

_ZERO = Decimal(0)


@dataclass(frozen=True)
class QualityFlag:
    """Un cuadre que no sale. Serializable tal cual a `raw_source_ref`."""

    key: str
    severity: Severity
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "severity": self.severity,
            "message": self.message,
            "evidence": self.evidence,
        }


# Totales y las partidas que como mínimo contienen. La comprobación es de UN
# solo lado —los componentes no pueden pasarse del total— porque casi todos los
# balances tienen partidas 'otros' que el canónico no modela: que los
# componentes sumen MENOS que el total es lo normal, no un error.
_COMPONENTS_OF: dict[str, tuple[str, ...]] = {
    "current_assets": ("cash", "current_financial_assets", "receivables", "inventory"),
    "current_liabilities": (
        "accounts_payable",
        "short_term_debt",
        "ltd_current_portion",
        "lease_liabilities_current",
    ),
    "total_assets": (
        "current_assets",
        "ppe_net",
        "goodwill",
        "intangibles",
        "deferred_tax_assets",
    ),
}


def _balance_identity(statement: CanonicalStatement) -> QualityFlag | None:
    """`activo == pasivo + patrimonio`, la identidad fundamental.

    Si `total_liabilities` se derivó como `activo − patrimonio`, la identidad se
    cumple POR CONSTRUCCIÓN y comprobarla no prueba nada. Ahí se emite un aviso
    de "no verificable" en vez de un OK mudo: una comprobación que no puede
    fallar, presentada como superada, es peor que no tenerla (misma trampa que
    la bandera `ebt_divergence` con el EBIT derivado).
    """
    assets, liabilities, equity = (
        statement.total_assets,
        statement.total_liabilities,
        statement.equity,
    )
    if assets is None or liabilities is None or equity is None or assets == _ZERO:
        return None

    if statement.provenance_of("total_liabilities") is Provenance.DERIVED:
        return QualityFlag(
            key="balance_identity_unverifiable",
            severity="info",
            message=(
                "El cuadre del balance no es verificable: el pasivo total no venía en el "
                "filing y se dedujo restando el patrimonio al activo, así que la identidad "
                "se cumple por construcción."
            ),
            evidence={"fiscal_year": statement.fiscal_year, "total_assets": str(assets)},
        )

    divergence = abs(assets - (liabilities + equity)) / abs(assets)
    if divergence <= BALANCE_TOLERANCE:
        return None
    return QualityFlag(
        key="balance_identity_broken",
        severity="amber",
        message=(
            f"El balance de {statement.fiscal_year} no cuadra: activo {assets:,.0f} frente a "
            f"pasivo + patrimonio {liabilities + equity:,.0f} ({divergence:.1%} de diferencia). "
            "Alguna partida se mapeó a un concepto que no le corresponde."
        ),
        evidence={
            "fiscal_year": statement.fiscal_year,
            "total_assets": str(assets),
            "total_liabilities": str(liabilities),
            "equity": str(equity),
            "divergence": str(divergence),
        },
    )


def _net_margin_in_range(statement: CanonicalStatement) -> QualityFlag | None:
    """El margen neto vive en [−1, 1] salvo catástrofe.

    Fuera de ahí no suele haber una empresa rara: hay una escala mal aplicada
    (miles frente a unidades) o un ingreso mapeado a una partida parcial.
    """
    revenue, net_income = statement.revenue, statement.net_income
    if revenue is None or net_income is None or revenue == _ZERO:
        return None
    margin = net_income / revenue
    if Decimal(-1) <= margin <= Decimal(1):
        return None
    return QualityFlag(
        key="net_margin_out_of_range",
        severity="amber",
        message=(
            f"El margen neto de {statement.fiscal_year} sale {margin:.0%}, fuera de lo "
            "posible para un negocio en marcha: probable error de escala o de mapeo de "
            "la cifra de negocio."
        ),
        evidence={
            "fiscal_year": statement.fiscal_year,
            "revenue": str(revenue),
            "net_income": str(net_income),
            "margin": str(margin),
        },
    )


def _components_within_total(statement: CanonicalStatement) -> list[QualityFlag]:
    """Ningún grupo de componentes puede pasarse de su total.

    Sumar más que el total solo puede significar que una etiqueta se está
    contando dos veces (típicamente un concepto agregado colado como si fuera de
    detalle). Al revés no se comprueba: casi todo balance tiene partidas 'otros'
    que el canónico no recoge.
    """
    flags: list[QualityFlag] = []
    for total_item, components in _COMPONENTS_OF.items():
        total = statement.get(total_item)
        if total is None or total <= _ZERO:
            continue
        present = {item: value for item in components if (value := statement.get(item)) is not None}
        if not present:
            continue
        subtotal = sum(present.values(), _ZERO)
        if subtotal <= total * (Decimal(1) + BALANCE_TOLERANCE):
            continue
        flags.append(
            QualityFlag(
                key="components_exceed_total",
                severity="amber",
                message=(
                    f"En {statement.fiscal_year} las partidas de '{total_item}' suman "
                    f"{subtotal:,.0f}, más que el propio total ({total:,.0f}): alguna "
                    "etiqueta se está contando dos veces."
                ),
                evidence={
                    "fiscal_year": statement.fiscal_year,
                    "total_item": total_item,
                    "total": str(total),
                    "components": {item: str(value) for item, value in present.items()},
                },
            )
        )
    return flags


#: Pares (partida grande, partida pequeña) que comparten unidad y guardan entre
#: sí una proporción acotada. No es una identidad contable: es una comprobación
#: de ORDEN DE MAGNITUD, que es justo lo que se rompe cuando dos partidas de la
#: misma naturaleza llegan en escalas distintas.
_SAME_SCALE_PAIRS: tuple[tuple[str, str, Decimal], ...] = (
    # Acciones medias del ejercicio vs acciones al cierre. Difieren por las
    # recompras del año —un 5% es mucho—, jamás por un factor de mil.
    ("shares_outstanding_eop", "shares_basic", Decimal(100)),
    ("shares_outstanding_eop", "shares_diluted", Decimal(100)),
    # Activo total vs patrimonio: el apalancamiento más extremo no llega a 100x.
    ("total_assets", "equity", Decimal(1000)),
)

SCALE_RATIO_ALARM = Decimal(1000)
"""A partir de aquí no es apalancamiento ni recompra: es un cambio de unidad."""


def _scale_coherence(statement: CanonicalStatement) -> list[QualityFlag]:
    """Partidas de la misma naturaleza que llegan en escalas distintas.

    El XBRL no distingue `746300000` de `746.3`: ambas declaran la unidad
    `shares`. Cuando un emisor cambia su presentación a millones —McDonald's lo
    hizo en el 10-K de 2023— nada en el fichero lo delata, y el número entra
    dividido por un millón sin romper ningún cuadre contable: el balance sigue
    cuadrando, los márgenes siguen en rango, y sólo se nota si alguien se fija
    en que la caja libre por acción son nueve millones de dólares.

    Este cuadre existe porque los otros tres miran identidades DENTRO de una
    misma magnitud y son ciegos a que dos magnitudes relacionadas hayan dejado
    de ser comparables entre sí.
    """
    flags: list[QualityFlag] = []
    for big_item, small_item, normal_ratio in _SAME_SCALE_PAIRS:
        big = getattr(statement, big_item, None)
        small = getattr(statement, small_item, None)
        if big is None or small is None or small == _ZERO or big == _ZERO:
            continue
        ratio = abs(big) / abs(small)
        if ratio < SCALE_RATIO_ALARM and ratio > (Decimal(1) / SCALE_RATIO_ALARM):
            continue
        flags.append(
            QualityFlag(
                key=f"scale_mismatch:{big_item}/{small_item}",
                severity="red",
                message=(
                    f"«{big_item}» y «{small_item}» deberían ser del mismo orden "
                    f"(como mucho {normal_ratio}x) y difieren {ratio:.0f}x: una de las dos "
                    "viene en otra unidad. Cualquier cálculo que las mezcle con importes "
                    "estará mal por ese factor."
                ),
                evidence={
                    "fiscal_year": statement.fiscal_year,
                    big_item: str(big),
                    small_item: str(small),
                    "ratio": str(ratio.quantize(Decimal("0.01"))),
                },
            )
        )
    return flags


def validate_statement(statement: CanonicalStatement) -> tuple[QualityFlag, ...]:
    """Todos los cuadres de un ejercicio. Sin banderas = todo cuadró.

    Nota sobre las imputaciones a cero: no hace falta revisar si rompen un cuadre.
    Los ceros solo entran en partidas de DETALLE, y un cero nunca hace que unos
    componentes se pasen de su total ni descuadra el balance — solo puede
    empequeñecer una suma. Lo que sí puede romper un cuadre es una partida
    DERIVADA, y por eso el cuadre del balance mira la procedencia del pasivo.
    """
    flags: list[QualityFlag] = []
    for check in (_balance_identity, _net_margin_in_range):
        flag = check(statement)
        if flag is not None:
            flags.append(flag)
    flags.extend(_components_within_total(statement))
    flags.extend(_scale_coherence(statement))
    return tuple(flags)
