"""Data-fix: rellena el tipo de cambio de las operaciones que quedaron en `1`.

**Por qué existe.** `inv_lots.fx_rate_at_trade` e `inv_sales.fx_rate_at_trade`
tenían `1` como valor por defecto del schema. Mientras la valoración no usaba FX
vivo ese `1` era inocuo —`fx_effect` salía siempre 0— pero al cablear el FX real
en PHASE-44.11.E pasó a afirmar «la compra se hizo a 1 USD = 1 EUR», y la
pantalla mostraba un efecto divisa que nadie había introducido. El alta ya lo
deriva del BCE (`portfolio.service.resolve_trade_fx`); esto arregla lo anterior.

**Por qué es un script y no una migración.** Lección [PHASE-34]: una migración
backfilea para REPRODUCIR el comportamiento previo, y la corrección de datos es
un paso separado y auditado. Además necesita las tasas del BCE, que viven en
`exchange_rates` y pueden requerir red — una migración no es sitio para eso.

Uso:
    python -m scripts.backfill_trade_fx            # dry-run: sólo informa
    python -m scripts.backfill_trade_fx --apply    # escribe

Sólo toca filas con `fx_rate_at_trade = 1` cuya divisa NO sea la base: un `1`
en un valor en euros es correcto, y un `1` que el usuario declaró a propósito en
un valor extranjero es indistinguible del default — se asume que no lo declaró,
que es lo que ocurre en la práctica (el campo no estaba en ningún formulario).
"""

from __future__ import annotations

import argparse
import asyncio
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.main  # noqa: F401  (ver nota)
from app.core.config import settings
from app.modules.currency import service as currency_service
from app.modules.investment.catalog.models import Security
from app.modules.investment.portfolio.models import Lot, Sale

# El import de `app.main` es por EFECTO LATERAL: registra todos los modelos en
# el metadata de SQLAlchemy. `inv_lots` tiene FK a `accounts` y a `users`, y sin
# esas tablas registradas el flush del `--apply` revienta con
# `NoReferencedTableError`. El dry-run no lo destapaba —hace un SELECT con el
# join explícito, que no necesita resolver la FK— así que este script se había
# probado sólo por la mitad. Se importa la app entera y no la lista de modelos
# porque esa lista ya está duplicada en `alembic/env.py` y `tests/conftest.py`;
# una tercera copia es una más que mantener sincronizada.

_ONE = Decimal(1)


async def _run(apply: bool) -> int:
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    changed = 0
    skipped = 0

    async with factory() as db:
        for model, label in ((Lot, "lote"), (Sale, "venta")):
            rows = (
                await db.execute(
                    select(model, Security.ticker, Security.currency)
                    .join(Security, Security.id == model.security_id)
                    .where(model.fx_rate_at_trade == _ONE)
                    .where(Security.currency != currency_service.CANONICAL_BASE)
                )
            ).all()

            for row, ticker, currency in rows:
                result = await currency_service.convert(
                    db,
                    amount=_ONE,
                    from_currency=currency,
                    to_currency=currency_service.CANONICAL_BASE,
                    at_date=row.trade_date,
                )
                if result.fallback == "missing":
                    # Sin flechas Unicode a propósito: la consola de Windows usa
                    # cp1252 por defecto y un `→` aborta el script con
                    # UnicodeEncodeError justo al imprimir el informe.
                    print(
                        f"  ! {label} {ticker} {row.trade_date}: sin tasa "
                        f"{currency}->{currency_service.CANONICAL_BASE}, se deja en 1"
                    )
                    skipped += 1
                    continue
                print(
                    f"  {label} {ticker} {row.trade_date}: 1 -> {result.rate} "
                    f"(tasa de {result.rate_date}, {result.fallback})"
                )
                if apply:
                    row.fx_rate_at_trade = result.rate
                changed += 1

        if apply:
            await db.commit()

    await engine.dispose()
    verb = "actualizadas" if apply else "se actualizarían"
    print(f"\n{changed} filas {verb}; {skipped} sin tasa disponible.")
    if not apply and changed:
        print("Dry-run. Repite con --apply para escribir.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="escribe (sin él, dry-run)")
    args = parser.parse_args()
    return asyncio.run(_run(args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
