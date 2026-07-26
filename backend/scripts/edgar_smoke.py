"""Smoke manual del adapter EDGAR (PHASE-44.6, ARCHITECTURE §7).

Recorre el pipeline COMPLETO de ingesta contra empresas reales —descarga →
anclaje anual → mapeo canónico → cuadres— y enseña el resultado por ejercicio.
Es la verificación en vivo que los tests no pueden hacer: ellos corren con
hechos sintéticos, y lo que aquí se comprueba es que la forma real de
`companyfacts` sigue encajando.

NO forma parte del engine ni de CI.

Uso:
    EDGAR_IDENTITY="Nombre email" python scripts/edgar_smoke.py MCD O JNJ

La primera vez descarga y deja el crudo en `EDGAR_CACHE_DIR`
(`backend/data/edgar_cache` por defecto). A partir de ahí corre offline: con la
cache poblada no hace falta ni identidad ni red.

Qué mirar en la salida:

- **`ebit`** debe salir `sourced` en MCD y `derived` en O y JNJ (ninguna de las
  dos publica ya resultado operativo).
- **`total_liabilities`** debe salir `derived` en MCD (no publica `Liabilities`),
  y con él el cuadre del balance como NO VERIFICABLE — nunca como superado.
- **El margen neto** debe rondar 31,9% (MCD), 18,4% (O) y 28,5% (JNJ).
- **Los huecos** deben ser ausencias reales: sin COGS en MCD y O (son
  servicios), sin activo corriente en O (balance no clasificado de REIT).
"""

from __future__ import annotations

import asyncio
import os
import sys
from decimal import Decimal
from pathlib import Path

from app.core.config import settings
from app.modules.investment.fundamentals.adapters.annual import build_raw_filings, filing_refs
from app.modules.investment.fundamentals.adapters.base import SecurityIdentity
from app.modules.investment.fundamentals.adapters.edgar import EdgarAdapter
from app.modules.investment.fundamentals.canonical import CANONICAL_ITEMS, Provenance
from app.modules.investment.fundamentals.normalization import normalize

# Lo que se imprime en detalle. El resto se resume como recuento de huecos: la
# tabla entera son 49 filas por ejercicio y lo que se está mirando es si las
# partidas VERTEBRALES salen y con qué procedencia.
SPOTLIGHT = (
    "total_assets",
    "total_liabilities",
    "equity",
    "revenue",
    "cogs",
    "ebit",
    "pretax_income",
    "interest_expense",
    "net_income",
    "cfo",
    "capex",
    "dividends_paid",
    "debt_change",
    "shares_outstanding_eop",
)


def _cache_dir() -> Path:
    configured = Path(settings.edgar_cache_dir)
    if configured.is_absolute():
        return configured
    return Path(__file__).resolve().parents[1] / configured


def _identity() -> str:
    return os.environ.get("EDGAR_IDENTITY") or settings.edgar_identity


def _fmt(value: Decimal | None) -> str:
    return "—  (HUECO)" if value is None else f"{value:>22,.0f}"


async def run(tickers: list[str]) -> None:
    adapter = EdgarAdapter(
        identity=_identity(),
        cache_dir=_cache_dir(),
        timeout_seconds=settings.edgar_timeout_seconds,
    )

    for ticker in tickers:
        # `TICKER:CIK` evita la resolución por red: con la cache poblada el
        # script corre entero sin tocar la SEC.
        if ":" in ticker:
            symbol, cik = ticker.split(":", 1)
            identity = SecurityIdentity(ticker=symbol.upper(), cik=cik.zfill(10), name=symbol)
        else:
            identity = await adapter.resolve(ticker)

        print(f"\n{'=' * 80}")
        print(f"{identity.ticker}  (CIK {identity.cik})  {identity.name}")
        print(
            f"  SIC {identity.sic}  ·  REIT={identity.is_reit}  ·  financiera={identity.is_financial}"
        )
        print("=" * 80)

        facts = await adapter.fetch_facts(identity)
        refs = filing_refs(facts)
        print(f"  {len(facts):,} hechos · {len(refs)} informes anuales")

        filings = build_raw_filings(facts, limit=settings.edgar_filings_back)
        if not filings:
            print("  sin ejercicios anuales utilizables")
            continue

        for raw in filings:
            statement = normalize(raw)
            holes = [item for item in CANONICAL_ITEMS if statement.get(item) is None]
            print(f"\n  ── FY{raw.fiscal_year}  (cierre {raw.fiscal_year_end}, {raw.currency})")
            print(f"     accession {raw.filing_accession} · {len(raw.facts):,} hechos anclados")

            for item in SPOTLIGHT:
                provenance = statement.provenance_of(item)
                mark = "" if provenance is Provenance.SOURCED else f"  [{provenance}]"
                print(f"     {item:<24} {_fmt(statement.get(item))}{mark}")

            revenue, net_income = statement.revenue, statement.net_income
            if revenue and net_income is not None:
                print(f"     {'margen neto':<24} {net_income / revenue:>21.1%}")

            print(f"     huecos: {len(holes)} → {', '.join(holes) if holes else '(ninguno)'}")
            for flag in statement.raw_source_ref["quality_flags"]:
                print(f"     ⚑ [{flag['severity']}] {flag['message']}")


if __name__ == "__main__":
    # La consola de Windows usa cp1252 por defecto y no sabe escribir los
    # caracteres de caja/viñeta del informe (─ · → ⚑). Forzamos UTF-8 en la
    # salida para que el smoke corra igual en Windows que en Linux/CI.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:] or ["MCD", "O", "JNJ"]
    asyncio.run(run(args))
