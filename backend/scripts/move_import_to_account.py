"""Data-fix: mueve las filas de un import a la cuenta correcta (y las restaura).

**Por qué existe.** Un extracto se puede importar eligiendo la cuenta
equivocada: el asistente no contrasta el contenido del fichero con la cuenta, y
el import termina sin un solo error. Medido: `julio criedito.pdf` (extracto de
la TARJETA) entró en la cuenta del BANCO, y julio fue el único mes en que la
tarjeta no recibió ninguna compra.

**Por qué mover y no reimportar.** Nada de lo que decide el import depende de la
cuenta: ni el `flow` (sale del signo del extracto y del texto) ni la categoría
(sale de mappings y reglas). Lo único que la cuenta gobierna es dónde aterrizan
las filas y el anclaje de saldo — y un extracto de tarjeta no trae columna
Saldo. Así que mover conserva exactamente el mismo resultado sin pedirle al
usuario el fichero otra vez.

Restaura de la papelera las filas que estuvieran borradas: este script se usa
después de `undo_card_statement_into_bank.py`, que las manda allí.

Uso:
    python -m scripts.move_import_to_account --job <uuid> --account "<nombre>"
    python -m scripts.move_import_to_account --job <uuid> --account "<nombre>" --apply
"""

from __future__ import annotations

import argparse
import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.main  # noqa: F401  — registra todos los modelos en el metadata
from app.core.config import settings
from app.modules.personal_finance.accounts.models import Account
from app.modules.personal_finance.accounts.repository import get_balances_for_user
from app.modules.personal_finance.imports.models import ImportJob
from app.modules.personal_finance.transactions.models import Transaction


async def _run(job_id: uuid.UUID, account_name: str, apply: bool) -> int:
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with factory() as db:
        job = await db.get(ImportJob, job_id)
        if job is None:
            print(f"No existe el job {job_id}")
            return 1

        destino = (
            await db.execute(
                select(Account).where(Account.user_id == job.user_id, Account.name == account_name)
            )
        ).scalar_one_or_none()
        if destino is None:
            print(f"No existe la cuenta {account_name!r}")
            return 1

        rows = (
            (
                await db.execute(
                    select(Transaction)
                    .where(
                        Transaction.user_id == job.user_id,
                        Transaction.created_at >= job.created_at,
                        Transaction.created_at <= job.updated_at,
                    )
                    .order_by(Transaction.occurred_at)
                )
            )
            .scalars()
            .all()
        )

        origen = (await get_balances_for_user(db, job.user_id)).get(destino.id)
        print(f"Job: {job.filename}  ->  cuenta «{destino.name}» ({destino.nature.value})")
        print(f"Filas: {len(rows)}  (en papelera: {sum(1 for r in rows if r.deleted_at)})")
        print(f"Movimiento actual de «{destino.name}»: {origen}")
        print()
        for r in rows:
            marca = "restaurar+mover" if r.deleted_at else "mover"
            flow = r.flow.value if r.flow else "(sin clasificar)"
            print(f"  {marca:<16} {r.occurred_at.date()} {r.amount:>8} {flow:<13} {r.description}")

        if not apply:
            print("\nDRY-RUN: no se ha escrito nada. Repite con --apply.")
            await engine.dispose()
            return 0

        for r in rows:
            r.deleted_at = None
            r.account_id = destino.id
        await db.commit()

        nuevo = (await get_balances_for_user(db, job.user_id)).get(destino.id)
        print(f"\nAPLICADO: {len(rows)} filas movidas a «{destino.name}».")
        print(f"Movimiento de «{destino.name}»: {origen}  ->  {nuevo}")

    await engine.dispose()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True, help="UUID del import_job")
    parser.add_argument("--account", required=True, help="nombre de la cuenta destino")
    parser.add_argument("--apply", action="store_true", help="escribe (por defecto: dry-run)")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(uuid.UUID(args.job), args.account, args.apply)))


if __name__ == "__main__":
    main()
