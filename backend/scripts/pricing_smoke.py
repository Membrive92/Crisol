"""Smoke EN VIVO del adapter de precios (PHASE-44.11.G). **Fuera de CI.**

Los tests del adapter monkeypatchean la librería: fijan lo que hacemos nosotros
con lo que devuelve, no que siga devolviéndolo. Este script es lo otro — toca
Yahoo de verdad contra cinco mercados y enseña el número para que se contraste
con el bróker. Es la comprobación que en PHASE-44.6 cazó el `getattr` sobre un
método, que ningún test sintético veía.

Uso (desde `backend/`, con el venv del proyecto):
    python -m scripts.pricing_smoke

No escribe en base de datos. Tarda ~10 s por el throttling deliberado.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

from app.modules.investment.pricing.adapters.base import Quote, QuoteError, QuoteRequest
from app.modules.investment.pricing.adapters.yfinance import YFinanceAdapter, to_yahoo_symbol

#: Un valor por mercado de la tabla de sufijos, más el caso que debe FALLAR.
CASES: list[tuple[str, str, str]] = [
    ("KO", "NYSE", "Coca-Cola — US, sin sufijo"),
    ("ULVR", "XLON", "Unilever — Londres, PENIQUES (la división ÷100)"),
    ("IBE", "XMAD", "Iberdrola — Madrid"),
    ("ALV", "XETR", "Allianz — Xetra"),
    ("MC", "XPAR", "LVMH — París"),
    ("XYZ", "XTKS", "Tokio — plaza sin mapeo, DEBE salir excluido"),
]


async def main() -> int:
    adapter = YFinanceAdapter(throttle_seconds=1.0)
    requests = [QuoteRequest(key=t, ticker=t, exchange=e) for t, e, _ in CASES]

    print("Símbolos que se van a pedir:")
    for ticker, exchange, note in CASES:
        symbol = to_yahoo_symbol(ticker, exchange)
        print(f"  {ticker:6} {exchange:6} → {symbol or '(sin mapeo)':10}  {note}")
    print("\nConsultando (1 req/s)…\n")

    results = await adapter.quotes(requests)

    ok = 0
    for ticker, exchange, _ in CASES:
        result = results[ticker]
        if isinstance(result, Quote):
            ok += 1
            prev = f"{result.prev_close}" if result.prev_close is not None else "—"
            print(f"  ✔ {ticker:6} {result.price:>12} {result.currency:4}  (cierre ant.: {prev})")
            if result.currency and not result.currency.isupper():
                print(f"    ⚠ divisa no normalizada: {result.currency!r} — debería ser ISO")
            if exchange == "XLON" and result.price > Decimal(500):
                print("    ⚠ precio sospechosamente alto para libras: ¿no se dividió?")
        elif isinstance(result, QuoteError):
            print(f"  ✘ {ticker:6} {result.reason}")

    print(f"\n{ok}/{len(CASES) - 1} mercados con cotización (el de Tokio debe fallar).")
    print("\nContrasta estos precios con tu bróker antes de dar la fase por buena.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
