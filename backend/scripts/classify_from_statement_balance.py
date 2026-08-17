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

**`--fix-contradictions` (PHASE-47.G).** Por defecto sólo mira filas SIN
dirección, que es el caso conservador: rellenar un hueco no puede empeorar nada.
Con esa opción mira también las que YA tienen dirección y **la corrige cuando el
extracto dice lo contrario**. Hace falta porque un signo equivocado no es un
hueco: cuenta el importe al revés, o sea el doble de error que perderlo. Las
DEVOLUCIONES caían ahí — el fichero las escribe en positivo sin `+`, y hasta
PHASE-47.G eso se leía como «no declara dirección» y mandaba la categoría, que
para un reembolso de Amazon dice «compras».

Va como opción y no por defecto porque sobrescribir una dirección existente
puede pisar una corrección que hizo el usuario a mano. La aritmética es la misma
y sigue exigiendo que sólo una hipótesis cuadre.

Uso:
    python -m scripts.classify_from_statement_balance --email <email>
    python -m scripts.classify_from_statement_balance --email <email> --apply
    ... --fix-contradictions          # además corrige las que van al revés
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
from app.modules.personal_finance.transactions.models import Transaction, TransactionFlow
from app.modules.personal_finance.transfers.service import classify_import_flow
from app.modules.users.models import User

#: Ventana donde buscar el saldo vecino. Amplia a propósito: la aritmética es
#: la que discrimina, no la cercanía — la ventana sólo acota el coste.
_WINDOW = timedelta(days=7)


def _current_direction(flow: TransactionFlow | None) -> bool | None:
    """`True` entrada, `False` salida, `None` sin dirección."""
    if flow in (TransactionFlow.IN, TransactionFlow.TRANSFER_IN):
        return True
    if flow in (TransactionFlow.OUT, TransactionFlow.TRANSFER_OUT):
        return False
    return None


async def _run(email: str, apply: bool, fix_contradictions: bool = False) -> int:
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with factory() as db:
        user_id = (
            await db.execute(select(User.id).where(User.email == email))
        ).scalar_one_or_none()
        if user_id is None:
            print(f"No existe el usuario {email}")
            return 1

        condiciones = [
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
            Transaction.statement_balance.is_not(None),
        ]
        if not fix_contradictions:
            condiciones.append(Transaction.flow.is_(None))
        pendientes = (
            (
                await db.execute(
                    select(Transaction).where(*condiciones).order_by(Transaction.occurred_at)
                )
            )
            .scalars()
            .all()
        )
        alcance = "con saldo de extracto" if fix_contradictions else "sin clasificar CON saldo"
        print(f"Filas {alcance}: {len(pendientes)}")

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
            if tx.statement_balance is None:  # el WHERE ya lo filtra; el tipo no lo sabe
                continue
            saldo: Decimal = tx.statement_balance
            entrada = (saldo - tx.amount) in saldos
            salida = (saldo + tx.amount) in saldos

            etiqueta = f"{tx.occurred_at.date()} {tx.amount} {tx.description!r}"
            actual = _current_direction(tx.flow)
            if entrada == salida:
                if actual is not None:
                    # Con dirección ya puesta y sin veredicto del extracto, no
                    # hay nada que decir: callarse evita enterrar los hallazgos.
                    continue
                motivo = "ninguna hipotesis cuadra" if not entrada else "cuadran las dos"
                print(f"  SALTO  {etiqueta} -> {motivo}, la dejo neutra")
                continue
            if actual is not None and actual == entrada:
                continue  # el extracto confirma lo que ya hay

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
            if actual is None:
                print(f"     flow = {flow.value}")
            else:
                anterior = tx.flow.value if tx.flow is not None else "?"
                print(f"     CONTRADICE al extracto: {anterior} -> {flow.value}")
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
    parser.add_argument(
        "--fix-contradictions",
        action="store_true",
        help="corrige tambien las filas cuya direccion contradice al extracto",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args.email, args.apply, args.fix_contradictions)))


if __name__ == "__main__":
    main()
