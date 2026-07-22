"""Cruzado EDGAR (PHASE-44.6, ARCHITECTURE §8, punto de parada (a)).

Script MANUAL de validación — NO forma parte del engine ni corre en CI. Descarga
los `companyfacts` XBRL de una o más empresas de la SEC y, para cada una de las
48 partidas canónicas (DESIGN §4), muestra QUÉ concepto us-gaap la alimentó y con
qué valor en el último 10-K, más los cuadres de `validation.py`.

Su salida es la tabla que el usuario revisa antes de fijar el `concept_map`
definitivo. Los conceptos de `CONCEPT_MAP` de aquí son CANDIDATOS de partida
(conocimiento de la taxonomía us-gaap); el cruzado los confirma o los corrige
con datos reales.

Uso:
    EDGAR_IDENTITY="Nombre email" python scripts/validate_edgar.py MCD O JNJ

La identidad se lee SOLO de la variable de entorno y viaja únicamente en el
header User-Agent que exige la SEC. No se escribe en disco.
"""

from __future__ import annotations

import gzip
import json
import os
import sys
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.modules.investment.fundamentals.canonical import (
    CANONICAL_BALANCE_ITEM_SET,
    CANONICAL_ITEMS,
)

CACHE_DIR = Path(os.environ.get("EDGAR_CACHE_DIR", "data/edgar_cache"))
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

# Partidas de flujo (duración anual) vs stock (instante de cierre). El resto de
# las 48 son de balance (stocks); estas son las de P&L y flujo de caja.
_SHARE_ITEMS = {"shares_basic", "shares_diluted", "shares_outstanding_eop"}

# Candidatos us-gaap por partida canónica. Orden = prioridad (gana el primero con
# dato). El cruzado dirá cuáles faltan o sobran.
CONCEPT_MAP: dict[str, list[str]] = {
    # ── Balance ──
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "current_financial_assets": [
        "ShortTermInvestments",
        "MarketableSecuritiesCurrent",
        "AvailableForSaleSecuritiesCurrent",
    ],
    "receivables": [
        "AccountsReceivableNetCurrent",
        "ReceivablesNetCurrent",
        "AccountsAndOtherReceivablesNetCurrent",
        "AccountsNotesAndLoansReceivableNetCurrent",  # MCD
        "AccountsReceivableNet",  # O — balance no clasificado, sin sufijo Current
    ],
    "inventory": ["InventoryNet"],
    "current_assets": ["AssetsCurrent"],
    "ppe_net": ["PropertyPlantAndEquipmentNet", "RealEstateInvestmentPropertyNet"],
    "goodwill": ["Goodwill"],
    "intangibles": [
        "IntangibleAssetsNetExcludingGoodwill",
        "FiniteLivedIntangibleAssetsNet",
    ],
    "deferred_tax_assets": [
        "DeferredIncomeTaxAssetsNet",
        "DeferredTaxAssetsNetNoncurrent",
    ],
    "total_assets": ["Assets"],
    "short_term_debt": ["ShortTermBorrowings", "DebtCurrent", "CommercialPaper"],
    "ltd_current_portion": [
        "LongTermDebtCurrent",
        "LongTermDebtAndCapitalLeaseObligationsCurrent",
    ],
    "accounts_payable": [
        "AccountsPayableCurrent",
        "AccountsPayableTradeCurrent",
        "AccountsPayableAndAccruedLiabilitiesCurrentAndNoncurrent",  # O
    ],
    "lease_liabilities_current": [
        "OperatingLeaseLiabilityCurrent",
        "FinanceLeaseLiabilityCurrent",
    ],
    "current_liabilities": ["LiabilitiesCurrent"],
    "long_term_debt": [
        "LongTermDebtNoncurrent",
        "LongTermDebt",
        "LongTermDebtAndCapitalLeaseObligations",
        "NotesPayable",  # O
    ],
    "lease_liabilities_noncurrent": [
        "OperatingLeaseLiabilityNoncurrent",
        "FinanceLeaseLiabilityNoncurrent",
    ],
    "deferred_tax_liabilities": [
        "DeferredIncomeTaxLiabilitiesNet",
        "DeferredTaxLiabilitiesNoncurrent",
    ],
    "total_liabilities": ["Liabilities"],
    "share_premium": [
        "AdditionalPaidInCapital",
        "AdditionalPaidInCapitalCommonStock",
        "CommonStocksIncludingAdditionalPaidInCapital",  # O — capital y prima en una línea
    ],
    "retained_earnings": [
        "RetainedEarningsAccumulatedDeficit",
        "AccumulatedDistributionsInExcessOfNetIncome",  # O — ¡signo invertido!, ver SIGN_FLIP
    ],
    "treasury_stock": ["TreasuryStockValue", "TreasuryStockCommonValue"],
    "equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    # ── Cuenta de resultados ──
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
    ],
    "cogs": ["CostOfGoodsAndServicesSold", "CostOfRevenue", "CostOfGoodsSold"],
    "sga_expense": [
        "SellingGeneralAndAdministrativeExpense",
        "GeneralAndAdministrativeExpense",
    ],
    "rd_expense": ["ResearchAndDevelopmentExpense"],
    "depreciation_amortization": [
        "DepreciationDepletionAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
        "DepreciationAndAmortization",
    ],
    "impairments": [
        "GoodwillImpairmentLoss",
        "ImpairmentOfLongLivedAssetsHeldForUse",
        "AssetImpairmentCharges",
    ],
    "gains_on_sale_of_business": [
        "GainLossOnDispositionOfBusiness",
        "GainLossOnSaleOfBusiness",
    ],
    "ebit": ["OperatingIncomeLoss"],
    "interest_expense": [
        "InterestExpense",
        "InterestExpenseNonoperating",  # JNJ
        "InterestExpenseOperating",  # O — dejó de usar InterestExpense tras 2024Q3
        "InterestExpenseDebt",
        "InterestAndDebtExpense",
    ],
    "pretax_income": [
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        # OJO: `...IncomeTaxesDomestic` NO va aquí. MCD no publica el pretax
        # consolidado, solo el desglose Domestic/Foreign; tomar el doméstico
        # como candidato daría 3.291 M$ donde el total son 10.897 M$ — un valor
        # PARCIAL presentado como total. Va en COMBINED_MAP, sumado al foreign.
    ],
    "taxes": ["IncomeTaxExpenseBenefit"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "shares_basic": ["WeightedAverageNumberOfSharesOutstandingBasic"],
    "shares_diluted": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
    "shares_outstanding_eop": ["CommonStockSharesOutstanding"],
    "sbc_expense": ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"],
    # ── Flujo de caja ──
    "cfo": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
    "wc_change_inventory": ["IncreaseDecreaseInInventories"],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "PaymentsToAcquireRealEstate",
        "PaymentsToAcquireCommercialRealEstate",  # O
    ],
    "acquisitions": ["PaymentsToAcquireBusinessesNetOfCashAcquired"],
    "divestitures": [
        "ProceedsFromDivestitureOfBusinesses",
        "ProceedsFromSaleOfProductiveAssets",
        "ProceedsFromSaleOfOtherProductiveAssets",  # MCD
        "ProceedsFromSaleOfPropertyPlantAndEquipment",
    ],
    "dividends_paid": [
        "PaymentsOfDividendsCommonStock",
        "PaymentsOfDividends",
        "PaymentsOfOrdinaryDividends",  # JNJ
    ],
    "buybacks": ["PaymentsForRepurchaseOfCommonStock"],
    "share_issuance": [
        "ProceedsFromIssuanceOfCommonStock",
        "ProceedsFromStockOptionsExercised",  # MCD
    ],
    "debt_change": [
        "ProceedsFromRepaymentsOfLongTermDebtAndCapitalSecurities",
        "ProceedsFromRepaymentsOfDebt",
    ],
    "taxes_paid": ["IncomeTaxesPaidNet", "IncomeTaxesPaid"],
}

# Conceptos que el filing reporta en POSITIVO pero que restan en su epígrafe.
# La ingesta debe normalizar el signo una sola vez (canonical.py, §4).
SIGN_FLIP: set[str] = {
    # O: "distribuciones en exceso del resultado" es un saldo DEUDOR del
    # patrimonio (un REIT reparte más de lo que gana), equivalente a reservas
    # negativas. Mapearlo tal cual daría reservas positivas de 10.500 M$.
    "AccumulatedDistributionsInExcessOfNetIncome",
}

# Partidas que NINGUNA empresa reporta con una sola etiqueta: hay que sumar un
# grupo y restar otro. Se aplica solo si el mapeo directo dejó hueco.
#
# Ojo con las trampas de nombre: `LongTermDebtMaturitiesRepaymentsOfPrincipal*`
# NO es un flujo de caja, es el calendario de vencimientos de la memoria. Un
# emparejado por subcadena "RepaymentsOf" se lo tragaría.
COMBINED_MAP: dict[str, dict[str, list[str]]] = {
    "debt_change": {
        "add": [
            "ProceedsFromIssuanceOfLongTermDebt",
            "ProceedsFromIssuanceOfSeniorLongTermDebt",
            "ProceedsFromShortTermDebt",
            "ProceedsFromRepaymentsOfShortTermDebt",  # ya es neto
            "ProceedsFromNotesPayable",
        ],
        "sub": [
            "RepaymentsOfLongTermDebt",
            "RepaymentsOfShortTermDebt",
            "RepaymentsOfNotesPayable",
            "RepaymentsOfUnsecuredDebt",
            "RepaymentsOfSecuredDebt",
        ],
    },
    # MCD publica el resultado antes de impuestos partido por jurisdicción y
    # nunca el consolidado. Sumarlos es la única forma de tener el total.
    "pretax_income": {
        "add": [
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesForeign",
        ],
        "sub": [],
    },
    # Balance no clasificado (O, y JNJ para operativo): la deuda por
    # arrendamiento viene sin partir corriente/no corriente. Se acumula toda en
    # el tramo no corriente porque la parte corriente es desconocida; afecta
    # solo a métricas de liquidez que estas empresas ya no pueden calcular.
    "lease_liabilities_noncurrent": {
        "add": ["OperatingLeaseLiability", "FinanceLeaseLiability"],
        "sub": [],
    },
}

# Partidas que NO viven en us-gaap sino en la taxonomía `dei` (datos de portada
# del filing). El adapter debe leer ambos namespaces, no solo us-gaap.
DEI_MAP: dict[str, list[str]] = {
    "shares_outstanding_eop": ["EntityCommonStockSharesOutstanding"],
}


# ── Derivaciones de ingesta (decididas en el cruzado, 2026-07-21) ─────
#
# Se aplican SOLO si la partida sale hueca del mapeo directo, y marcan la
# procedencia como `derived` (Provenance.DERIVED del canónico): aplican una
# identidad contable exacta, no inventan un dato ausente.


def _derive_ebit(values: dict[str, Decimal | None]) -> Decimal | None:
    """`ebit = pretax_income + interest_expense`.

    `OperatingIncomeLoss` no es fiable en XBRL: JNJ dejó de reportarlo en 2015
    y los REIT no tienen línea de resultado operativo.

    Usa el pretax REPORTADO (partida canónica 49, PHASE-44.6) y solo si falta
    cae a reconstruirlo como `net_income + taxes` — que ignora minoritarios y
    actividades discontinuadas, y por eso es el segundo plato.

    ⚠️ Efecto sobre `ebt_divergence_flag`: al derivar así, `ebit − intereses`
    es idénticamente igual al EBT, luego la bandera NUNCA dispararía. Por eso
    el adapter marca `ebit` como `derived` y el engine no evalúa la bandera
    salvo que el EBIT venga sourced (ver `derivations.ebt_divergence_flag`).
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
    """`total_liabilities = total_assets − equity` (identidad de balance).

    MCD no reporta `Liabilities` (sí `LiabilitiesAndStockholdersEquity`, que es
    el activo). Su patrimonio es NEGATIVO por recompras, y el engine ya maneja
    equity ≤ 0 con guardas.

    ⚠️ Efecto sobre el cuadre de balance: derivado así, activo == pasivo +
    patrimonio por construcción. El cuadre deja de ser una comprobación y pasa
    a ser 'no verificable' — no un OK.
    """
    total_assets, equity = values.get("total_assets"), values.get("equity")
    if total_assets is None or equity is None:
        return None
    return total_assets - equity


DERIVATIONS = {"ebit": _derive_ebit, "total_liabilities": _derive_total_liabilities}


def _identity() -> str:
    ident = os.environ.get("EDGAR_IDENTITY")
    if not ident:
        sys.exit("Falta EDGAR_IDENTITY (formato 'Nombre email') — la SEC lo exige.")
    return ident


def _get(url: str) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": _identity(), "Accept-Encoding": "gzip, deflate"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return bytes(raw)


def resolve_ciks(tickers: list[str]) -> dict[str, str]:
    """Ticker → CIK. Admite `TICKER:CIK` para no pegarle a la red.

    Con la forma explícita el script corre entero contra la cache local, sin
    `EDGAR_IDENTITY` y sin tocar data.sec.gov — útil para re-cruzar el mapeo.
    """
    explicit = {t.split(":")[0].upper(): t.split(":")[1].zfill(10) for t in tickers if ":" in t}
    pending = [t for t in tickers if ":" not in t]
    if not pending:
        return explicit

    data = json.loads(_get(TICKERS_URL))
    by_ticker = {row["ticker"]: str(row["cik_str"]).zfill(10) for row in data.values()}
    out: dict[str, str] = dict(explicit)
    for ticker in pending:
        cik = by_ticker.get(ticker.upper())
        if cik is None:
            sys.exit(f"Ticker {ticker} no está en el índice de la SEC")
        out[ticker.upper()] = cik
    return out


def fetch_facts(cik: str) -> dict[str, Any]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = CACHE_DIR / f"CIK{cik}.json"
    if cached.exists():
        payload: dict[str, Any] = json.loads(cached.read_text(encoding="utf-8"))
        return payload
    raw = _get(FACTS_URL.format(cik=cik))
    cached.write_bytes(raw)
    fresh: dict[str, Any] = json.loads(raw)
    return fresh


def _annual_points(concept: dict[str, Any], *, unit: str) -> list[dict[str, Any]]:
    """Datapoints de 10-K anuales (form 10-K, fp FY) de una unidad dada."""
    points = []
    for datum in concept.get("units", {}).get(unit, []):
        if datum.get("form") != "10-K" or datum.get("fp") != "FY":
            continue
        points.append(datum)
    return points


def _is_annual_duration(datum: dict[str, Any]) -> bool:
    """Un flujo anual dura ~1 año (descarta trimestres y YTD parciales)."""
    start, end = datum.get("start"), datum.get("end")
    if not start or not end:
        return False
    from datetime import date

    days = (date.fromisoformat(end) - date.fromisoformat(start)).days
    return 350 <= days <= 380


def target_fiscal_year_end(facts: dict[str, Any]) -> str | None:
    """El cierre fiscal más reciente, anclado en Assets (siempre presente)."""
    assets = facts.get("facts", {}).get("us-gaap", {}).get("Assets")
    if assets is None:
        return None
    ends = [d["end"] for d in _annual_points(assets, unit="USD")]
    return max(ends) if ends else None


def extract(facts: dict[str, Any], item: str, fye: str) -> tuple[str | None, Decimal | None]:
    """(concepto usado, valor) para una partida canónica en el cierre `fye`."""
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    is_stock = item in CANONICAL_BALANCE_ITEM_SET
    is_share = item in _SHARE_ITEMS
    unit = "shares" if is_share else "USD"

    for candidate in CONCEPT_MAP.get(item, []):
        concept = us_gaap.get(candidate)
        if concept is None:
            continue
        for datum in _annual_points(concept, unit=unit):
            if datum["end"] != fye:
                continue
            if not is_stock and not is_share and not _is_annual_duration(datum):
                continue
            value = Decimal(str(datum["val"]))
            if candidate in SIGN_FLIP:
                value = -value
            return candidate, value
    return None, None


def extract_combined(
    facts: dict[str, Any], item: str, fye: str
) -> tuple[str | None, Decimal | None]:
    """Suma de un grupo de etiquetas menos otro (`COMBINED_MAP`)."""
    spec = COMBINED_MAP.get(item)
    if spec is None:
        return None, None
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    is_stock = item in CANONICAL_BALANCE_ITEM_SET
    total = Decimal(0)
    used: list[str] = []

    for sign, tags in ((1, spec["add"]), (-1, spec["sub"])):
        for tag in tags:
            concept = us_gaap.get(tag)
            if concept is None:
                continue
            for datum in _annual_points(concept, unit="USD"):
                if datum["end"] != fye:
                    continue
                if not is_stock and not _is_annual_duration(datum):
                    continue
                total += sign * Decimal(str(datum["val"]))
                used.append(f"{'+' if sign > 0 else '-'}{tag}")
                break

    if not used:
        return None, None
    return " ".join(used), total


def extract_dei(facts: dict[str, Any], item: str) -> tuple[str | None, Decimal | None]:
    """Partidas de la taxonomía `dei` (portada). El `end` de la portada es la
    fecha de la cubierta del 10-K, POSTERIOR al cierre fiscal, así que no se
    puede anclar al `fye`: se toma el datapoint más reciente del último 10-K."""
    dei = facts.get("facts", {}).get("dei", {})
    for tag in DEI_MAP.get(item, []):
        concept = dei.get(tag)
        if concept is None:
            continue
        for unit in ("shares", "USD"):
            points = [d for d in concept.get("units", {}).get(unit, []) if d.get("form") == "10-K"]
            if points:
                latest = max(points, key=lambda d: (d.get("end", ""), d.get("filed", "")))
                return f"dei:{tag}", Decimal(str(latest["val"]))
    return None, None


def _fmt(value: Decimal | None) -> str:
    return "—  (HUECO)" if value is None else f"{value:>20,.0f}"


def check_balance(values: dict[str, Decimal | None], derived: set[str]) -> str:
    a = values.get("total_assets")
    liab = values.get("total_liabilities")
    eq = values.get("equity")
    if a is None or liab is None or eq is None or a == 0:
        return "cuadre balance: sin datos suficientes"
    if "total_liabilities" in derived:
        return (
            "cuadre balance: NO VERIFICABLE - `total_liabilities` se derivo de "
            "activo menos patrimonio, asi que el cuadre es tautologico"
        )
    diff = abs(a - (liab + eq)) / abs(a)
    mark = "OK" if diff < Decimal("0.01") else "!! DESCUADRE"
    return f"cuadre balance: activo {a:,.0f} vs pasivo+patrimonio {liab + eq:,.0f} (dif {diff:.2%}) {mark}"


def check_margin(values: dict[str, Decimal | None]) -> str:
    rev = values.get("revenue")
    ni = values.get("net_income")
    if rev is None or ni is None or rev == 0:
        return "margen neto: sin datos"
    margin = ni / rev
    mark = "OK" if Decimal(-1) <= margin <= Decimal(1) else "!! FUERA DE RANGO"
    return f"margen neto: {margin:.1%} {mark}"


def run(tickers: list[str]) -> None:
    ciks = resolve_ciks(tickers)
    missing_any: dict[str, list[str]] = {item: [] for item in CANONICAL_ITEMS}

    for ticker, cik in ciks.items():
        facts = fetch_facts(cik)
        name = facts.get("entityName", "?")
        fye = target_fiscal_year_end(facts)
        print(f"\n{'=' * 78}\n{ticker}  (CIK {cik})  {name}  —  cierre {fye}\n{'=' * 78}")
        if fye is None:
            print("  sin Assets anuales: no se puede anclar el año fiscal")
            continue

        values: dict[str, Decimal | None] = {}
        labels: dict[str, str] = {}
        for item in CANONICAL_ITEMS:
            concept, value = extract(facts, item, fye)
            values[item] = value
            labels[item] = concept or f"(ninguno de {len(CONCEPT_MAP.get(item, []))} candidatos)"

        # Rescates sobre lo que quedó hueco: combinación de etiquetas y dei.
        for item in CANONICAL_ITEMS:
            if values[item] is not None:
                continue
            concept, value = extract_combined(facts, item, fye)
            if value is None:
                concept, value = extract_dei(facts, item)
            if value is not None:
                values[item], labels[item] = value, concept or "?"

        # Derivaciones: solo sobre lo que quedó hueco tras el mapeo directo.
        derived: set[str] = set()
        for item, derive in DERIVATIONS.items():
            if values.get(item) is not None:
                continue
            value = derive(values)
            if value is None:
                continue
            values[item] = value
            derived.add(item)
            labels[item] = "(DERIVADA — provenance=derived)"

        for item in CANONICAL_ITEMS:
            if values[item] is None:
                missing_any[item].append(ticker)
            print(f"  {item:<28} {_fmt(values[item])}   {labels[item]}")

        print(f"\n  {check_balance(values, derived)}")
        print(f"  {check_margin(values)}")
        if derived:
            print(f"  derivadas: {', '.join(sorted(derived))}")

    print(
        f"\n{'=' * 78}\nRESUMEN — partidas con hueco en alguna empresa (revisar mapeo):\n{'=' * 78}"
    )
    any_missing = False
    for item, where in missing_any.items():
        if where:
            any_missing = True
            print(f"  {item:<28} falta en: {', '.join(where)}")
    if not any_missing:
        print("  (ninguna — todas las partidas mapearon en las 3 empresas)")


if __name__ == "__main__":
    args = sys.argv[1:] or ["MCD", "O", "JNJ"]
    run(args)
