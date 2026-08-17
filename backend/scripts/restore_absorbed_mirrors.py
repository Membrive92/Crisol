"""Data-fix: devolver a la vida los "cargos espejo" que sí eran del extracto.

**Por qué existe.** Hasta PHASE-47.F, registrar una operación financiada como
deuda borraba el cargo del mismo importe que la compensaba y además anulaba el
abono en el saldo: dos correcciones para un solo hecho. Retirada la mecánica,
las filas que siguen borradas dejan el saldo por encima del extracto justo en su
importe. Éstas hay que devolverlas.

**Qué NO hace.** No adivina. La pregunta «¿esta línea estaba en el extracto de
esta cuenta?» tiene una respuesta comprobable —`statement_balance`, que PHASE-39
guarda por fila cuando el fichero trae la columna Saldo— y sólo se restaura lo
que la tenga. Una fila sin saldo no es «falsa»: es DESCONOCIDA, y las conocidas
de este usuario resultaron venir del extracto de la tarjeta importado por error
en el banco. Se listan para que las decida una persona.

**Por qué es un script y no una migración.** Lección [PHASE-34]: una migración
reproduce el comportamiento previo; la corrección de datos es un paso separado y
auditado.

Uso:
    cd backend && .venv/Scripts/python.exe -m scripts.restore_absorbed_mirrors
    ... --apply           # escribe
    ... --apply --reanchor  # además re-deriva el opening desde el ancla guardada

`--reanchor` restaura el invariante `saldo(fecha del ancla) == lo que dijo el
banco` (`re_anchor_from_stored`). Hace falta porque cambiar el modelo cambia
Σmov, igual que importar historia vieja. Va aparte a propósito: conviene mirar
la diferencia ANTES de que el opening la absorba, porque es la única señal de
cuánta historia falta por importar.
"""

from __future__ import annotations

import argparse
import asyncio
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.main  # noqa: F401  (efecto lateral: registra todos los modelos)
from app.core.config import settings
from app.modules.personal_finance.accounts.models import Account, AccountNature
from app.modules.personal_finance.accounts.repository import get_balances_for_user
from app.modules.personal_finance.accounts.service import re_anchor_from_stored
from app.modules.personal_finance.transactions.models import Transaction
from app.modules.personal_finance.transfers.service import classify_import_flow


async def run(*, apply: bool, reanchor: bool) -> int:
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as db:
            rows = (
                (
                    await db.execute(
                        select(Transaction, Account)
                        .join(Account, Account.id == Transaction.account_id)
                        .where(Transaction.absorbed_as_mirror.is_(True))
                        .order_by(Transaction.occurred_at)
                    )
                )
                .tuples()
                .all()
            )
            if not rows:
                print("No hay ningún cargo espejo absorbido.")
                return 0

            restored: list[tuple[Transaction, Account]] = []
            unknown: list[tuple[Transaction, Account]] = []
            for tx, account in rows:
                (restored if tx.statement_balance is not None else unknown).append((tx, account))

            print(f"{len(rows)} fila(s) marcadas como cargo espejo absorbido.\n")

            if restored:
                print("SE RESTAURAN - el extracto de su cuenta las lleva (traen saldo):")
                for tx, account in restored:
                    print(
                        f"  {tx.occurred_at.date()}  {tx.amount:>10}  {account.name:<22} "
                        f"saldo {tx.statement_balance}  {(tx.description or '')[:38]}"
                    )
                print()

            if unknown:
                print("NO SE TOCAN - sin saldo en la fila, asi que no consta que sean de")
                print("esa cuenta. Decidelas mirando el extracto:")
                for tx, account in unknown:
                    print(
                        f"  {tx.occurred_at.date()}  {tx.amount:>10}  {account.name:<22} "
                        f"{(tx.description or '')[:44]}"
                    )
                print()

            if not apply:
                print("Dry-run: no se ha escrito nada. Repite con --apply.")
                return 0

            for tx, _account in restored:
                tx.deleted_at = None
                tx.absorbed_as_mirror = False
                # El `flow` guardado es de la época en que la fila entró, y a las
                # liquidaciones de entonces les tocaba `OUT`. Revivirla con ese
                # valor la metería como gasto del mes; se reclasifica con el
                # criterio de hoy, que las reconoce como movimiento interno.
                reclassified = classify_import_flow(
                    bank_sign=-1,
                    text=tx.description,
                    category_is_transfer=False,
                )
                if reclassified is not None:
                    tx.flow = reclassified
            await db.flush()

            if reanchor:
                assets = (
                    (await db.execute(select(Account).where(Account.nature == AccountNature.ASSET)))
                    .scalars()
                    .all()
                )
                for account in assets:
                    if await re_anchor_from_stored(db, account.user_id, account.id):
                        print(f"Ancla re-derivada: {account.name}")

            await db.commit()
            print(f"\nRestauradas {len(restored)} fila(s).")

            balances = await get_balances_for_user(db, rows[0][1].user_id)
            for account in {a.id: a for _t, a in rows}.values():
                total = (account.opening_balance or Decimal(0)) + balances.get(
                    account.id, Decimal(0)
                )
                print(f"  {account.name}: {total} (extracto {account.anchored_statement_balance})")
    finally:
        await engine.dispose()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="escribe los cambios")
    parser.add_argument(
        "--reanchor",
        action="store_true",
        help="además re-deriva el opening de cada activo desde su ancla guardada",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(apply=args.apply, reanchor=args.reanchor)))


if __name__ == "__main__":
    main()
