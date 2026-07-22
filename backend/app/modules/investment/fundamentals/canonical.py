"""Modelo canónico de un estado financiero (PHASE-44.2, ARCHITECTURE §1, DESIGN §4).

`CanonicalStatement` es la representación PURA (sin SQLAlchemy) de una fila de
`financial_statements`: las 49 partidas canónicas del DESIGN §4, todas
`Decimal | None`. Un hueco es `None`, JAMÁS 0 implícito [Dec.4, §4.5].

Es la frontera entre la INGESTA (que normaliza signos y escalas una sola vez) y
el ENGINE (puro, sin BD ni red — ARCHITECTURE §0.1). El engine consume ESTE
tipo, nunca el modelo ORM: así se puede testear con sintéticos sin levantar BD.

Convención de signos (la fija la ingesta, §4): **todas las partidas positivas
con semántica fija** — `capex` > 0 = inversión, `dividends_paid` > 0 = pago,
`buybacks` > 0 = recompra.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from app.modules.investment.enums import AccountingStd

# ── Procedencia ───────────────────────────────────────────────────────


class Provenance(enum.StrEnum):
    """De dónde sale un importe. Se propaga a cada `MetricResult` para que el
    informe pueda decir "esto es un proxy", no solo "esto vale X".

    Orden de degradación: SOURCED < DERIVED < IMPUTED_ZERO < ESTIMATED. Al
    combinar inputs, gana el MÁS degradado (ver `combine_provenance`)."""

    SOURCED = "sourced"
    """Viene del filing tal cual (tras normalizar signo y escala)."""
    DERIVED = "derived"
    """Calculada a partir de otras partidas con una regla explícita (§4.4).
    No inventa información: aplica una identidad contable exacta, y por eso
    degrada menos que suponer un dato que no está."""
    IMPUTED_ZERO = "imputed_zero"
    """Cero supuesto ante un concepto AUSENTE en el filing (§4.5).

    En XBRL las empresas omiten los conceptos que valen cero (sin deuda a corto
    → no etiquetan el concepto), así que tratar toda ausencia como hueco dejaría
    `total_debt` sin calcular en compañías perfectamente sanas. La imputación la
    decide la INGESTA con una lista blanca (ARCHITECTURE §3.3), nunca el engine:
    aquí solo se propaga. No cuenta como `sourced` en la completitud."""
    ESTIMATED = "estimated"
    """Proxy declarado. Hoy solo `maintenance_capex` [Dec.4]: es un proxy
    honesto, y por eso JAMÁS cuenta como hueco de datos."""


_PROVENANCE_RANK: dict[Provenance, int] = {
    Provenance.SOURCED: 0,
    Provenance.DERIVED: 1,
    Provenance.IMPUTED_ZERO: 2,
    Provenance.ESTIMATED: 3,
}
"""Por qué este orden: `derived` aplica una identidad exacta sobre sus inputs
(no añade supuestos), mientras que `imputed_zero` inventa un valor a partir de
una ausencia — supuesto fuerte, aunque con una prior alta. `estimated` es el más
débil: un proxy con fórmula propia. Que `imputed_zero` esté por encima de
`sourced` es lo que garantiza que una imputación nunca se presente como dato
sourced, tal y como exige el §4.5."""


def combine_provenance(*provenances: Provenance) -> Provenance:
    """Procedencia resultante de combinar inputs: la más degradada.

    Un ratio que usa una partida `estimated` es `estimated`, por muy sourced que
    sea el resto. Sin inputs → SOURCED (elemento neutro).
    """
    if not provenances:
        return Provenance.SOURCED
    return max(provenances, key=lambda p: _PROVENANCE_RANK[p])


# ── Catálogo de partidas canónicas (49) ───────────────────────────────

CANONICAL_BALANCE_ITEMS: tuple[str, ...] = (
    # Activo corriente
    "cash",
    "current_financial_assets",
    "receivables",
    "inventory",
    "current_assets",
    # Activo no corriente
    "ppe_net",
    "goodwill",
    "intangibles",
    "deferred_tax_assets",
    "total_assets",
    # Pasivo corriente
    "short_term_debt",
    "ltd_current_portion",
    "accounts_payable",
    "lease_liabilities_current",
    "current_liabilities",
    # Pasivo no corriente
    "long_term_debt",
    "lease_liabilities_noncurrent",
    "deferred_tax_liabilities",
    "total_liabilities",
    # Patrimonio
    "share_premium",
    "retained_earnings",
    "treasury_stock",
    "equity",
)

CANONICAL_INCOME_ITEMS: tuple[str, ...] = (
    "revenue",
    "cogs",
    "sga_expense",
    "rd_expense",
    "depreciation_amortization",
    "impairments",
    "gains_on_sale_of_business",
    "ebit",
    "interest_expense",
    "pretax_income",
    "taxes",
    "net_income",
    "shares_basic",
    "shares_diluted",
    "shares_outstanding_eop",
    "sbc_expense",
)

CANONICAL_CASHFLOW_ITEMS: tuple[str, ...] = (
    "cfo",
    "wc_change_inventory",
    "capex",
    "acquisitions",
    "divestitures",
    "dividends_paid",
    "buybacks",
    "share_issuance",
    "debt_change",
    "taxes_paid",
)

CANONICAL_ITEMS: tuple[str, ...] = (
    CANONICAL_BALANCE_ITEMS + CANONICAL_INCOME_ITEMS + CANONICAL_CASHFLOW_ITEMS
)
"""Las 49 partidas canónicas, en el orden del DESIGN §4. Fuente de verdad
compartida por engine, normalización y tests — para que 'qué partidas hay' no
se escriba dos veces y diverja.

`pretax_income` es la 49ª y la añadió PHASE-44.6: el cruzado con EDGAR mostró
que `OperatingIncomeLoss` no es fiable en XBRL (JNJ dejó de publicarlo en 2015,
los REIT no tienen línea operativa), así que el EBIT hay que derivarlo del
resultado antes de impuestos. Con el pretax REPORTADO la derivación no depende
de reconstruirlo con `net_income + taxes` —que ignora minoritarios y actividades
discontinuadas— y la bandera `ebt_divergence` conserva dos fuentes que comparar."""

CANONICAL_BALANCE_ITEM_SET: frozenset[str] = frozenset(CANONICAL_BALANCE_ITEMS)
CANONICAL_ITEM_SET: frozenset[str] = frozenset(CANONICAL_ITEMS)


# ── El estado financiero canónico ─────────────────────────────────────


@dataclass(frozen=True)
class CanonicalStatement:
    """Un año fiscal de una empresa, ya normalizado. Inmutable: el engine no
    muta sus inputs (ARCHITECTURE §0.1).

    Todas las partidas por defecto `None` para que los sintéticos de test
    declaren solo lo que el caso necesita: lo no declarado es explícitamente un
    HUECO, y las métricas que lo usen saldrán `not_computable` con razón.
    """

    fiscal_year: int
    fiscal_year_end: date
    accounting_std: AccountingStd
    currency: str = "USD"
    filing_accession: str = ""

    # ── Balance (23) ──────────────────────────────────────────────
    cash: Decimal | None = None
    current_financial_assets: Decimal | None = None
    receivables: Decimal | None = None
    inventory: Decimal | None = None
    current_assets: Decimal | None = None
    ppe_net: Decimal | None = None
    goodwill: Decimal | None = None
    intangibles: Decimal | None = None
    deferred_tax_assets: Decimal | None = None
    total_assets: Decimal | None = None
    short_term_debt: Decimal | None = None
    ltd_current_portion: Decimal | None = None
    accounts_payable: Decimal | None = None
    lease_liabilities_current: Decimal | None = None
    current_liabilities: Decimal | None = None
    long_term_debt: Decimal | None = None
    lease_liabilities_noncurrent: Decimal | None = None
    deferred_tax_liabilities: Decimal | None = None
    total_liabilities: Decimal | None = None
    share_premium: Decimal | None = None
    retained_earnings: Decimal | None = None
    treasury_stock: Decimal | None = None
    equity: Decimal | None = None

    # ── Cuenta de resultados (16, acciones incluidas) ──────────────
    revenue: Decimal | None = None
    cogs: Decimal | None = None
    sga_expense: Decimal | None = None
    rd_expense: Decimal | None = None
    depreciation_amortization: Decimal | None = None
    impairments: Decimal | None = None
    gains_on_sale_of_business: Decimal | None = None
    ebit: Decimal | None = None
    interest_expense: Decimal | None = None
    pretax_income: Decimal | None = None
    taxes: Decimal | None = None
    net_income: Decimal | None = None
    shares_basic: Decimal | None = None
    shares_diluted: Decimal | None = None
    shares_outstanding_eop: Decimal | None = None
    sbc_expense: Decimal | None = None

    # ── Flujo de caja (10) ────────────────────────────────────────
    cfo: Decimal | None = None
    wc_change_inventory: Decimal | None = None
    capex: Decimal | None = None
    acquisitions: Decimal | None = None
    divestitures: Decimal | None = None
    dividends_paid: Decimal | None = None
    buybacks: Decimal | None = None
    share_issuance: Decimal | None = None
    debt_change: Decimal | None = None
    taxes_paid: Decimal | None = None

    item_provenance: dict[str, Provenance] = field(default_factory=dict)
    """Excepciones a "todo lo del filing es SOURCED". Vacío = todas sourced.

    Lo rellena la INGESTA: `imputed_zero` para los conceptos ausentes que la
    lista blanca permite suponer 0 (§4.5), o `derived` cuando reconstruye una
    partida desde sus componentes. El engine solo lee y propaga."""

    raw_source_ref: dict[str, Any] = field(default_factory=dict)
    """Conceptos XBRL originales sin colapsar [Dec.13] — auditar el mapeo."""

    def get(self, item: str) -> Decimal | None:
        """Valor de una partida canónica por nombre.

        Valida el nombre contra el catálogo: un typo ('recievables') sería si no
        un `None` silencioso que convierte la métrica en `not_computable` sin
        que nadie se entere.
        """
        if item not in CANONICAL_ITEM_SET:
            raise KeyError(f"'{item}' no es una partida canónica (DESIGN §4)")
        value: Decimal | None = getattr(self, item)
        return value

    def provenance_of(self, item: str) -> Provenance:
        """Procedencia de una partida. Por defecto SOURCED."""
        if item not in CANONICAL_ITEM_SET:
            raise KeyError(f"'{item}' no es una partida canónica (DESIGN §4)")
        return self.item_provenance.get(item, Provenance.SOURCED)
