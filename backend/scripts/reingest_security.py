"""Re-ingesta de un valor con el pipeline actual (PHASE-44.12).

**Por qué existe.** La corrección de escala de acciones vive en la
normalización, así que los estados YA persistidos siguen con el dato viejo: el
arreglo del código no reescribe la base. Este script vuelve a pasar los crudos
por el pipeline y persiste el resultado.

Usa la caché de crudos de `data/edgar_cache/` cuando existe, así que
normalmente NO toca la SEC: lo que se re-ejecuta es la normalización, que es
donde estaba el fallo.

Uso (desde `backend/`, con el venv del proyecto):
    python -m scripts.reingest_security MCD          # dry-run: compara y no escribe
    python -m scripts.reingest_security MCD --apply  # persiste
"""

from __future__ import annotations

import argparse
import asyncio
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.modules.investment.catalog.models import Security
from app.modules.investment.fundamentals.adapters.factory import get_fundamentals_adapter
from app.modules.investment.fundamentals.models import FinancialStatement
from app.modules.investment.fundamentals.service import ingest_fundamentals
from app.modules.users.models import User

#: Partidas cuya escala cambió el arreglo. Se comparan antes/después.
_WATCHED = ("shares_basic", "shares_diluted", "shares_outstanding_eop")


def _snapshot(rows: list[FinancialStatement]) -> dict[int, dict[str, Decimal | None]]:
    return {r.fiscal_year: {item: getattr(r, item, None) for item in _WATCHED} for r in rows}


async def _run(ticker: str, apply: bool) -> int:
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with factory() as db:
        security = (
            await db.execute(select(Security).where(Security.ticker == ticker.upper()))
        ).scalar_one_or_none()
        if security is None:
            print(f"No existe {ticker.upper()} en el catálogo.")
            await engine.dispose()
            return 1

        security_id = security.id
        # `securities` es una tabla GLOBAL sin `user_id` [Dec.11], pero el
        # `IngestionJob` sí es del usuario. Se toma el primero que exista: el
        # job es una traza de auditoría de la descarga, y los estados que
        # produce son globales igualmente.
        user_id = (await db.execute(select(User.id).limit(1))).scalar_one_or_none()
        if user_id is None:
            print("No hay usuarios en la base; el job de ingesta necesita uno.")
            await engine.dispose()
            return 1

        before = _snapshot(
            list(
                (
                    await db.execute(
                        select(FinancialStatement)
                        .where(FinancialStatement.security_id == security_id)
                        .order_by(FinancialStatement.fiscal_year)
                    )
                ).scalars()
            )
        )

    print(f"{ticker.upper()} — ANTES:")
    for year, items in sorted(before.items()):
        print(f"  {year}  " + "  ".join(f"{k}={v}" for k, v in items.items()))

    if not apply:
        print("\nDry-run: no se ha escrito nada. Repite con --apply para re-ingerir.")
        await engine.dispose()
        return 0

    async with factory() as db:
        adapter = get_fundamentals_adapter()
        job = await ingest_fundamentals(
            db,
            security_id=security_id,
            user_id=user_id,
            filings_back=settings.edgar_filings_back,
            adapter=adapter,
        )
        await db.commit()
        print(f"\nJob {job.status}" + (f" — {job.error}" if job.error else ""))

    async with factory() as db:
        after = _snapshot(
            list(
                (
                    await db.execute(
                        select(FinancialStatement)
                        .where(FinancialStatement.security_id == security_id)
                        .order_by(FinancialStatement.fiscal_year)
                    )
                ).scalars()
            )
        )

    print(f"\n{ticker.upper()} — DESPUÉS:")
    for year, items in sorted(after.items()):
        marks = []
        for k, v in items.items():
            old = before.get(year, {}).get(k)
            mark = " <-- CAMBIA" if old is not None and v is not None and old != v else ""
            marks.append(f"{k}={v}{mark}")
        print(f"  {year}  " + "  ".join(marks))

    await engine.dispose()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticker", help="ticker del catálogo, p. ej. MCD")
    parser.add_argument("--apply", action="store_true", help="persiste (sin él, dry-run)")
    args = parser.parse_args()
    return asyncio.run(_run(args.ticker, args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
