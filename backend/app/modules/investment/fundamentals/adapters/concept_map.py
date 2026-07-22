"""Mapeo XBRL → partidas canónicas (PHASE-44.6, ARCHITECTURE §3.2).

Este módulo es DATOS: qué etiqueta de la taxonomía alimenta cada una de las 49
partidas canónicas. La lógica que lo aplica vive en `normalization.py`, y la
descarga en `adapters/edgar.py`. Aquí no hay red ni reloj — se puede testear
entero sin `edgartools` y sin tocar la SEC.

El mapeo NO se escribió de memoria: sale del cruzado de `scripts/validate_edgar.py`
contra tres empresas reales elegidas por lo que rompen (PHASE-44.6):

| Ticker | CIK | Qué estresa |
|--------|-----|-------------|
| MCD | 0000063908 | patrimonio NEGATIVO por recompras; no publica `Liabilities` |
| O (Realty Income) | 0000726728 | REIT: balance NO clasificado, sin línea operativa |
| JNJ | 0000200406 | dejó de publicar `OperatingIncomeLoss` en 2015; línea NETA de deterioros |

## Los cuatro mecanismos

El diseño original preveía uno solo —una lista de candidatos, gana el primero
con dato—, y el cruzado demostró que no basta. En orden de aplicación:

1. **Candidatos** (`CONCEPT_MAP`): lista ordenada por prioridad dentro de
   `us-gaap`. El primero que tenga dato en el ejercicio gana.
2. **Combinación** (`COMBINED_MAP`): partidas que NINGUNA de las tres reporta
   con una sola etiqueta; hay que sumar un grupo y restar otro.
3. **Namespace `dei`** (`DEI_MAP`): datos de portada del filing que no viven en
   `us-gaap`.
4. **Normalización de signo** (`SIGN_FLIP`): etiquetas que el emisor publica en
   positivo pero que restan en su epígrafe.

Más un quinto caso, que no es de mapeo sino de desagregación: `NET_LINE_FALLBACKS`,
para cuando el emisor publica UNA línea neta donde el canónico tiene dos partidas
de signo opuesto.

Lo que este módulo NO hace: derivar partidas ausentes (eso es `normalization.py`,
con procedencia `derived`) ni suponer ceros (la lista blanca `IMPUTABLE_ZERO_ITEMS`
la aplica también `normalization.py`).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from app.modules.investment.fundamentals.canonical import (
    CANONICAL_ITEM_SET,
    Provenance,
)

US_GAAP = "us-gaap"
DEI = "dei"
"""Los dos namespaces XBRL que lee la ingesta. `dei` (Document and Entity
Information) es la portada del filing, no el estado financiero."""


def qualify(namespace: str, tag: str) -> str:
    """Clave de un hecho XBRL: `'us-gaap:Assets'`.

    Los hechos llegan a `normalization.py` con el namespace por delante porque
    una etiqueta puede existir en los dos (y porque `dei` publica en la fecha de
    cubierta, no en la de cierre: mezclarlas sin distinguir sería un error mudo).
    """
    return f"{namespace}:{tag}"


# ── 1. Candidatos us-gaap por partida ─────────────────────────────────

CONCEPT_MAP: Mapping[str, tuple[str, ...]] = {
    # ── Balance ──
    "cash": (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ),
    "current_financial_assets": (
        "ShortTermInvestments",
        "MarketableSecuritiesCurrent",
        "AvailableForSaleSecuritiesCurrent",
    ),
    "receivables": (
        "AccountsReceivableNetCurrent",
        "ReceivablesNetCurrent",
        "AccountsAndOtherReceivablesNetCurrent",
        "AccountsNotesAndLoansReceivableNetCurrent",  # MCD
        "AccountsReceivableNet",  # O — balance no clasificado, sin sufijo Current
    ),
    "inventory": ("InventoryNet",),
    "current_assets": ("AssetsCurrent",),
    "ppe_net": ("PropertyPlantAndEquipmentNet", "RealEstateInvestmentPropertyNet"),
    "goodwill": ("Goodwill",),
    "intangibles": (
        "IntangibleAssetsNetExcludingGoodwill",
        "FiniteLivedIntangibleAssetsNet",
    ),
    "deferred_tax_assets": (
        "DeferredIncomeTaxAssetsNet",
        "DeferredTaxAssetsNetNoncurrent",
    ),
    "total_assets": ("Assets",),
    "short_term_debt": ("ShortTermBorrowings", "DebtCurrent", "CommercialPaper"),
    "ltd_current_portion": (
        "LongTermDebtCurrent",
        "LongTermDebtAndCapitalLeaseObligationsCurrent",
    ),
    "accounts_payable": (
        "AccountsPayableCurrent",
        "AccountsPayableTradeCurrent",
        "AccountsPayableAndAccruedLiabilitiesCurrentAndNoncurrent",  # O
    ),
    "lease_liabilities_current": (
        "OperatingLeaseLiabilityCurrent",
        "FinanceLeaseLiabilityCurrent",
    ),
    "current_liabilities": ("LiabilitiesCurrent",),
    "long_term_debt": (
        "LongTermDebtNoncurrent",
        "LongTermDebt",
        "LongTermDebtAndCapitalLeaseObligations",
        "NotesPayable",  # O
    ),
    "lease_liabilities_noncurrent": (
        "OperatingLeaseLiabilityNoncurrent",
        "FinanceLeaseLiabilityNoncurrent",
    ),
    "deferred_tax_liabilities": (
        "DeferredIncomeTaxLiabilitiesNet",
        "DeferredTaxLiabilitiesNoncurrent",
    ),
    "total_liabilities": ("Liabilities",),
    "share_premium": (
        "AdditionalPaidInCapital",
        "AdditionalPaidInCapitalCommonStock",
        "CommonStocksIncludingAdditionalPaidInCapital",  # O — capital y prima juntos
    ),
    "retained_earnings": (
        "RetainedEarningsAccumulatedDeficit",
        "AccumulatedDistributionsInExcessOfNetIncome",  # O — ¡signo invertido!, ver SIGN_FLIP
    ),
    "treasury_stock": ("TreasuryStockValue", "TreasuryStockCommonValue"),
    "equity": (
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ),
    # ── Cuenta de resultados ──
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
    ),
    "cogs": ("CostOfGoodsAndServicesSold", "CostOfRevenue", "CostOfGoodsSold"),
    "sga_expense": (
        "SellingGeneralAndAdministrativeExpense",
        "GeneralAndAdministrativeExpense",
    ),
    "rd_expense": ("ResearchAndDevelopmentExpense",),
    "depreciation_amortization": (
        "DepreciationDepletionAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
        "DepreciationAndAmortization",
    ),
    "impairments": (
        "GoodwillImpairmentLoss",
        "ImpairmentOfLongLivedAssetsHeldForUse",
        "AssetImpairmentCharges",
    ),
    "gains_on_sale_of_business": (
        "GainLossOnDispositionOfBusiness",
        "GainLossOnSaleOfBusiness",
    ),
    "ebit": ("OperatingIncomeLoss",),
    "interest_expense": (
        "InterestExpense",
        "InterestExpenseNonoperating",  # JNJ
        "InterestExpenseOperating",  # O — abandonó InterestExpense tras 2024Q3
        "InterestExpenseDebt",
        "InterestAndDebtExpense",
    ),
    "pretax_income": (
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        # OJO: `...IncomeTaxesDomestic` NO va aquí. MCD no publica el pretax
        # consolidado, solo el desglose Domestic/Foreign; tomar el doméstico como
        # candidato daría 3.291 M$ donde el total son 10.897 M$ — un valor PARCIAL
        # presentado como total, que es peor que un hueco. Va en COMBINED_MAP.
    ),
    "taxes": ("IncomeTaxExpenseBenefit",),
    "net_income": ("NetIncomeLoss", "ProfitLoss"),
    "shares_basic": ("WeightedAverageNumberOfSharesOutstandingBasic",),
    "shares_diluted": ("WeightedAverageNumberOfDilutedSharesOutstanding",),
    "shares_outstanding_eop": ("CommonStockSharesOutstanding",),
    "sbc_expense": ("ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"),
    # ── Flujo de caja ──
    "cfo": (
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ),
    "wc_change_inventory": ("IncreaseDecreaseInInventories",),
    "capex": (
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "PaymentsToAcquireRealEstate",
        "PaymentsToAcquireCommercialRealEstate",  # O
    ),
    "acquisitions": ("PaymentsToAcquireBusinessesNetOfCashAcquired",),
    "divestitures": (
        "ProceedsFromDivestitureOfBusinesses",
        "ProceedsFromSaleOfProductiveAssets",
        "ProceedsFromSaleOfOtherProductiveAssets",  # MCD
        "ProceedsFromSaleOfPropertyPlantAndEquipment",
    ),
    "dividends_paid": (
        "PaymentsOfDividendsCommonStock",
        "PaymentsOfDividends",
        "PaymentsOfOrdinaryDividends",  # JNJ
    ),
    "buybacks": ("PaymentsForRepurchaseOfCommonStock",),
    "share_issuance": (
        "ProceedsFromIssuanceOfCommonStock",
        "ProceedsFromStockOptionsExercised",  # MCD
    ),
    "debt_change": (
        "ProceedsFromRepaymentsOfLongTermDebtAndCapitalSecurities",
        "ProceedsFromRepaymentsOfDebt",
    ),
    "taxes_paid": ("IncomeTaxesPaidNet", "IncomeTaxesPaid"),
}
"""Candidatos `us-gaap` por partida, en orden de prioridad. Gana el primero con
dato en el ejercicio.

El orden no es cosmético: los candidatos van de la etiqueta más específica a la
más laxa. `CashAndCashEquivalentsAtCarryingValue` antes que la variante que
INCLUYE efectivo restringido, porque el restringido no es caja disponible; leerlo
primero inflaría la liquidez de cualquier empresa que publique las dos."""


# ── 2. Combinación de etiquetas ───────────────────────────────────────


@dataclass(frozen=True)
class CombinedSpec:
    """Partida que se arma sumando un grupo de etiquetas y restando otro.

    `provenance` NO es siempre la misma, y la diferencia importa: sumar las dos
    jurisdicciones del pretax de MCD reconstruye el total EXACTO que la empresa
    no publica agregado (sigue siendo dato reportado, `sourced`), mientras que
    meter toda la deuda por arrendamiento en el tramo no corriente porque el
    balance no está clasificado es un SUPUESTO (`derived`).
    """

    add: tuple[str, ...]
    sub: tuple[str, ...] = ()
    provenance: Provenance = Provenance.SOURCED
    note: str = ""


COMBINED_MAP: Mapping[str, CombinedSpec] = {
    "debt_change": CombinedSpec(
        add=(
            "ProceedsFromIssuanceOfLongTermDebt",
            "ProceedsFromIssuanceOfSeniorLongTermDebt",
            "ProceedsFromShortTermDebt",
            "ProceedsFromRepaymentsOfShortTermDebt",  # ya viene neto
            "ProceedsFromNotesPayable",
        ),
        sub=(
            "RepaymentsOfLongTermDebt",
            "RepaymentsOfShortTermDebt",
            "RepaymentsOfNotesPayable",
            "RepaymentsOfUnsecuredDebt",
            "RepaymentsOfSecuredDebt",
        ),
        note=(
            "Ninguna de las tres empresas del cruzado publica la variación neta de "
            "deuda con una sola etiqueta: hay que sumar emisiones y restar "
            "amortizaciones (MCD −72 M$ · O +1.064,6 M$ · JNJ +9.637 M$)."
        ),
    ),
    "pretax_income": CombinedSpec(
        add=(
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesForeign",
        ),
        note=(
            "MCD publica el resultado antes de impuestos partido por jurisdicción y "
            "nunca el consolidado. Sumar las dos es la única forma de tener el total."
        ),
    ),
    "lease_liabilities_noncurrent": CombinedSpec(
        add=("OperatingLeaseLiability", "FinanceLeaseLiability"),
        provenance=Provenance.DERIVED,
        note=(
            "Balance no clasificado (el REIT): la deuda por arrendamiento viene sin "
            "partir corriente/no corriente. Se acumula toda en el tramo no corriente "
            "porque la parte corriente es DESCONOCIDA — es un supuesto, no una "
            "identidad, y por eso degrada a `derived`. Solo afecta a métricas de "
            "liquidez que estas empresas ya no pueden calcular de todos modos."
        ),
    ),
}
"""Partidas que hay que armar combinando etiquetas.

⚠️ Trampa de nombre que costó un rato en el cruzado:
`LongTermDebtMaturitiesRepaymentsOfPrincipal*` **no** es un flujo de caja, es el
calendario de vencimientos de la memoria. Un emparejado por subcadena
'RepaymentsOf' se lo tragaría y contaría la deuda futura como amortización del
ejercicio. Por eso las listas son explícitas y jamás por prefijo."""


# ── 3. Namespace `dei` ────────────────────────────────────────────────

DEI_MAP: Mapping[str, tuple[str, ...]] = {
    "shares_outstanding_eop": ("EntityCommonStockSharesOutstanding",),
}
"""Partidas que no están en `us-gaap` sino en la portada del filing.

Ni MCD ni JNJ publican `CommonStockSharesOutstanding` en us-gaap; las acciones en
circulación solo aparecen en la cubierta del 10-K. Su fecha (`end`) es la de la
cubierta, POSTERIOR al cierre fiscal, así que el adapter no puede anclarlas al
cierre como al resto: son el dato más reciente del filing, no el del ejercicio."""


# ── 4. Normalización de signo ─────────────────────────────────────────

SIGN_FLIP: frozenset[str] = frozenset(
    {
        # O: "distribuciones en exceso del resultado" es un saldo DEUDOR del
        # patrimonio (un REIT reparte más de lo que gana), equivalente a reservas
        # negativas. Mapearlo tal cual daría +10.528 M$ de reservas donde hay
        # -10.528 M$, y con ello un patrimonio que no cuadra con nada.
        "AccumulatedDistributionsInExcessOfNetIncome",
    }
)
"""Etiquetas que el emisor publica en positivo pero que RESTAN en su epígrafe.

La convención canónica es "todas las partidas positivas con semántica fija"
(`canonical.py`), y el sitio donde se aplica es la ingesta, una sola vez."""


# ── 5. Líneas netas que mezclan dos partidas canónicas ────────────────


@dataclass(frozen=True)
class NetLineSpec:
    """Una etiqueta NETA que mezcla dos partidas canónicas de signo opuesto.

    JNJ publica `GainLossOnSalesOfAssetsAndAssetImpairmentCharges` (263 M$): un
    neto de plusvalías por ventas y deterioros. El canónico las tiene separadas
    porque `ebit_clean = ebit + impairments − gains` las trata al revés, así que
    alimentar las dos partidas con la misma línea neta doblaría el ajuste.

    Regla: preferir SIEMPRE las etiquetas partidas; solo si la partida `into`
    quedó hueca se usa la neta, y entonces `zeroed` se fija a cero **con bandera**
    para que el informe pueda decir que el desglose no estaba disponible.
    """

    concept: str
    into: str
    zeroed: str
    reason: str


NET_LINE_FALLBACKS: tuple[NetLineSpec, ...] = (
    NetLineSpec(
        concept="GainLossOnSalesOfAssetsAndAssetImpairmentCharges",
        into="impairments",
        zeroed="gains_on_sale_of_business",
        reason=(
            "El emisor publica deterioros y plusvalías por venta en una sola línea "
            "neta, sin desglose. Se imputa el neto a los deterioros y las plusvalías "
            "quedan a cero: el ajuste de `ebit_clean` es correcto en magnitud "
            "agregada, pero el desglose no es auditable."
        ),
    ),
)


# ── Ausencia vs cero ──────────────────────────────────────────────────

IMPUTABLE_ZERO_ITEMS: frozenset[str] = frozenset(
    {
        "short_term_debt",
        "ltd_current_portion",
        "lease_liabilities_current",
        "lease_liabilities_noncurrent",
        "current_financial_assets",
        "inventory",
        "goodwill",
        "intangibles",
        "deferred_tax_assets",
        "deferred_tax_liabilities",
        "treasury_stock",
        "share_premium",
        "rd_expense",
        "sbc_expense",
        "impairments",
        "gains_on_sale_of_business",
        "acquisitions",
        "divestitures",
        "buybacks",
        "share_issuance",
        "dividends_paid",
        "debt_change",
        "wc_change_inventory",
    }
)
"""Partidas cuya AUSENCIA en el filing se puede leer como cero (§4.5, Dec.4).

En XBRL las empresas no etiquetan lo que vale cero: una compañía sin deuda a
corto sencillamente no publica el concepto. Tratar toda ausencia como hueco
dejaría `total_debt` sin calcular en empresas perfectamente sanas.

El criterio para entrar en la lista es que la ausencia sea INFORMATIVA: nadie se
olvida de publicar su fondo de comercio, así que no tenerlo significa no tenerlo.
Lo que queda FUERA es igual de deliberado: `revenue`, `cogs`, `current_assets`,
`equity` o `cfo` ausentes no significan cero, significan que este filing no los
da (un balance no clasificado no tiene `AssetsCurrent`, y un servicio no tiene
COGS) — y ahí la respuesta honesta es `not_computable`, no un cero que
convertiría un margen imposible en un número creíble.

Mención aparte para `long_term_debt`, que NO está y podría parecer que debería:
es la imputación más peligrosa del módulo. Si la empresa etiqueta su deuda con
un concepto que este mapeo no recoge, un cero por ausencia no daría un hueco
visible sino una empresa SIN DEUDA — con todo el bloque de apalancamiento
impecable. Un hueco se ve; una empresa sana falsa, no."""

CONDITIONAL_ZERO_ITEMS: Mapping[str, tuple[str, ...]] = {
    "interest_expense": ("short_term_debt", "ltd_current_portion", "long_term_debt"),
}
"""Partidas que solo se imputan a cero si sus condicionantes suman cero.

Una empresa SIN deuda no paga intereses, y ahí el cero es real. Con deuda viva,
un gasto financiero ausente es un fallo de mapeo disfrazado: imputarlo a cero
regalaría una cobertura de intereses infinita justo en la empresa apalancada
donde esa métrica es la que importa.

La regla es más estrecha de lo que parece, y es intencionado: como
`long_term_debt` no es imputable a cero (ver arriba), un condicionante DESCONOCIDO
no cuenta como cero y el gasto financiero se queda hueco. Solo se imputa cuando
el emisor publica explícitamente su deuda a largo en cero. Encadenar ausencias
—no publica deuda, luego no tiene, luego no paga intereses— es exactamente como
se fabrica una empresa impecable que no lo es."""


# ── Validación del propio mapeo ───────────────────────────────────────


@dataclass(frozen=True)
class _MapAudit:
    """Resultado de auditar el mapeo, para que el error diga QUÉ está mal."""

    problems: list[str] = field(default_factory=list)


def _audit() -> _MapAudit:
    audit = _MapAudit()
    for name, keys in (
        ("CONCEPT_MAP", CONCEPT_MAP.keys()),
        ("COMBINED_MAP", COMBINED_MAP.keys()),
        ("DEI_MAP", DEI_MAP.keys()),
        ("IMPUTABLE_ZERO_ITEMS", IMPUTABLE_ZERO_ITEMS),
        ("CONDITIONAL_ZERO_ITEMS", CONDITIONAL_ZERO_ITEMS.keys()),
    ):
        unknown = sorted(set(keys) - CANONICAL_ITEM_SET)
        if unknown:
            audit.problems.append(f"{name} referencia partidas inexistentes: {unknown}")

    for spec in NET_LINE_FALLBACKS:
        unknown = sorted({spec.into, spec.zeroed} - CANONICAL_ITEM_SET)
        if unknown:
            audit.problems.append(f"NET_LINE_FALLBACKS referencia partidas inexistentes: {unknown}")

    seen: dict[str, str] = {}
    for item, candidates in CONCEPT_MAP.items():
        for tag in candidates:
            if tag in seen:
                audit.problems.append(
                    f"la etiqueta '{tag}' alimenta '{seen[tag]}' y '{item}': "
                    "una misma etiqueta en dos partidas dobla el dato"
                )
            seen[tag] = item

    overlap = sorted(set(IMPUTABLE_ZERO_ITEMS) & set(CONDITIONAL_ZERO_ITEMS))
    if overlap:
        audit.problems.append(
            f"{overlap} está en la lista incondicional Y en la condicional: "
            "la incondicional ganaría y la condición no se evaluaría nunca"
        )
    return audit


_AUDIT = _audit()
if _AUDIT.problems:  # pragma: no cover — un fallo aquí rompe el import, que es el punto
    raise RuntimeError("concept_map inconsistente:\n  - " + "\n  - ".join(_AUDIT.problems))
