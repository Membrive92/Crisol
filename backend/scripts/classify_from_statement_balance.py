"""Data-fix: da dirección a las tx SIN clasificar usando el saldo del extracto.

**Por qué existe.** PHASE-46 enseñó al import a deducir la dirección del salto
de la columna Saldo cuando el extracto no trae signos, pero eso sólo actúa al
importar. Las filas que ya entraron sin dirección siguen ahí, neutras: no suman
ni restan en ningún sitio, así que no rompen nada, pero tampoco cuentan lo que
de verdad pasó.

**Cómo decide, sin depender del orden.** Una fila con saldo `S` e importe `A`
sólo puede ser una entrada (si existe otra fila del extracto con saldo `S − A`,
la de antes) o una salida (si existe una con `S + A`). Se comprueban las DOS
hipótesis y se exige que se cumpla exactamente una: si ninguna cuadra, entre
medias hay un movimiento sin saldo y no se toca nada; si cuadran las dos, el
extracto no distingue y tampoco se toca. Así no hace falta reconstruir el orden
del fichero, que es la parte frágil.

La dirección deducida se pasa al clasificador de producción
(`classify_import_flow`), no se escribe a mano: así la transfer-ness de la fila
sale de la misma regla que el resto y no de una copia que puede divergir.

Uso:
    python -m scripts.classify_from_statement_balance --email <email>
    python -m scripts.classify_from_statement_balance --email <email> --apply
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.main  # noqa: F401  — registra todos los modelos en el metadata
from app.core.config import settings
from app.modules.personal_finance.categories.models import Category
from app.modules.personal_finance.transactions.models import Transaction
from app.modules.personal_finance.transfers.service import classify_import_flow
from app.modules.users.models import User

#: Ventana donde buscar el saldo vecino. Amplia a propósito: la aritmética es
#: la que discrimina, no la cercanía — la ventana sólo acota el coste.
_WINDOW = timedelta(days=7)


async def _run(email: str, apply: bool) -> int:
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with factory() as db:
        user_id = (
            await db.execute(select(User.id).where(User.email == email))
        ).scalar_one_or_none()
        if user_id is None:
            print(f"No existe el usuario {email}")
            return 1

        pendientes = (
            (
                await db.execute(
                    select(Transaction).where(
                        Transaction.user_id == user_id,
                        Transaction.deleted_at.is_(None),
                        Transaction.flow.is_(None),
                        Transaction.statement_balance.is_not(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        print(f"Filas sin clasificar CON saldo de extracto: {len(pendientes)}")

        cambiadas = 0
        for tx in pendientes:
            saldos = set(
                (
                    await db.execute(
                        select(Transaction.statement_balance).where(
                            Transaction.user_id == user_id,
                            Transaction.account_id == tx.account_id,
                            Transaction.deleted_at.is_(None),
                            Transaction.id != tx.id,
                            Transaction.statement_balance.is_not(None),
                            Transaction.occurred_at >= tx.occurred_at - _WINDOW,
                            Transaction.occurred_at <= tx.occurred_at + _WINDOW,
                        )
                    )
                )
                .scalars()
                .all()
            )
            saldo: Decimal = tx.statement_balance
            entrada = (saldo - tx.amount) in saldos
            salida = (saldo + tx.amount) in saldos

            etiqueta = f"{tx.occurred_at.date()} {tx.amount} {tx.description!r}"
            if entrada == salida:
                motivo = "ninguna hipotesis cuadra" if not entrada else "cuadran las dos"
                print(f"  SALTO  {etiqueta} -> {motivo}, la dejo neutra")
                continue

            categoria_transfer = False
            if tx.category_id is not None:
                cat = await db.get(Category, tx.category_id)
                categoria_transfer = bool(cat and cat.is_transfer)

            flow = classify_import_flow(
                bank_sign=1 if entrada else -1,
                text=tx.description,
                category_is_transfer=categoria_transfer,
            )
            if flow is None:
                print(f"  SALTO  {etiqueta} -> el clasificador sigue sin decidir")
                continue

            vecino = saldo - tx.amount if entrada else saldo + tx.amount
            print(f"  {etiqueta}")
            print(f"     saldo {vecino} -> {saldo}  =  {'+' if entrada else '-'}{tx.amount}")
            print(f"     flow = {flow.value}")
            if apply:
                tx.flow = flow
            cambiadas += 1

        if apply:
            await db.commit()
            print(f"\nAPLICADO: {cambiadas} filas clasificadas.")
        else:
            print(f"\nDRY-RUN: {cambiadas} filas se clasificarian. Repite con --apply.")

    await engine.dispose()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--apply", action="store_true", help="escribe (por defecto: dry-run)")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args.email, args.apply)))


if __name__ == "__main__":
    main()
