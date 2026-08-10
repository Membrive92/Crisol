"""Data-fix: deshace la importación del extracto de TARJETA en la cuenta del BANCO.

**Por qué existe.** `julio criedito.pdf` (extracto de la tarjeta) se importó
eligiendo la cuenta BBVA en vez de `Tarjeta BBVA credito`. Efecto medido: julio
fue el único mes en que la tarjeta no recibió NI UNA compra (mayo 7, junio 7,
julio 0) y 17 compras de tarjeta quedaron colgando del banco. Además, el
aplazamiento del recibo entró por partida doble —una vez desde el extracto de la
tarjeta y otra desde el del banco—, y el enlace con la deuda quedó colgando de
la copia equivocada.

Deja el terreno listo para reimportar el PDF a la cuenta correcta:

1. **Deshace el enlace** de la operación financiada y manda su contrapartida a
   la papelera. La fila que representa el dinero entrando en el banco es la del
   extracto de la CUENTA, no la del de la tarjeta.
2. **Manda a la papelera** las filas del job. Es soft-delete: reversible desde
   la papelera, y `find_existing_hashes` no las cuenta como existentes, así que
   la reimportación las traerá de vuelta.
3. **Limpia `absorbed_as_mirror`** del cargo espejo. Esa marca existe para que
   reimportar el mismo extracto no resucite un cargo ya absorbido (AUDIT-2026-07
   H-04) y es correcta en su caso; aquí es justo lo contrario, porque queremos
   que la línea vuelva —en la cuenta buena—. Sin este paso la reimportación la
   saltaría en silencio y a la tarjeta le faltaría un movimiento.

**Por qué un script y no SQL a mano.** El paso 1 tiene que usar el servicio
(`unlink`), no un `UPDATE`: el par vive en dos filas y desemparejar sólo una
deja la otra apuntando al vacío.

Uso:
    python -m scripts.undo_card_statement_into_bank --job <uuid>            # dry-run
    python -m scripts.undo_card_statement_into_bank --job <uuid> --apply
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.main  # noqa: F401  — registra todos los modelos en el metadata
from app.core.config import settings
from app.modules.personal_finance.accounts.models import Account
from app.modules.personal_finance.imports.models import ImportJob
from app.modules.personal_finance.transactions.models import Transaction
from app.modules.personal_finance.transfers.service import unlink


async def _run(job_id: uuid.UUID, apply: bool) -> int:
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with factory() as db:
        job = await db.get(ImportJob, job_id)
        if job is None:
            print(f"No existe el job {job_id}")
            return 1
        print(f"Job: {job.filename}  ({job.rows_ok} filas OK)  creado {job.created_at}")

        # Las filas del job se identifican por su ventana de creacion: no hay FK
        # de transaction -> import_job, y anadirla ahora seria una migracion para
        # un arreglo de una vez.
        window_start = job.created_at
        window_end = job.updated_at
        rows = (
            (
                await db.execute(
                    select(Transaction)
                    .where(
                        Transaction.user_id == job.user_id,
                        Transaction.created_at >= window_start,
                        Transaction.created_at <= window_end,
                    )
                    .order_by(Transaction.occurred_at)
                )
            )
            .scalars()
            .all()
        )
        print(f"Filas encontradas en la ventana del job: {len(rows)}")

        cuentas = {
            a.id: a.name
            for a in (
                (await db.execute(select(Account).where(Account.user_id == job.user_id)))
                .scalars()
                .all()
            )
        }

        emparejadas = [r for r in rows if r.transfer_pair_id is not None]
        espejos = [r for r in rows if r.absorbed_as_mirror]
        vivas = [r for r in rows if r.deleted_at is None]

        print()
        print("PLAN")
        for r in emparejadas:
            pareja = await db.get(Transaction, r.transfer_pair_id)
            destino = cuentas.get(pareja.account_id, "?") if pareja else "?"
            print(f"  1. Deshacer enlace: {r.occurred_at.date()} {r.description!r}")
            print(f"     y mandar a la papelera su contrapartida en «{destino}»")
        for r in espejos:
            print(f"  3. Limpiar marca de espejo: {r.occurred_at.date()} {r.description!r}")
        print(f"  2. Mandar a la papelera {len(vivas)} filas vivas del job")

        if not apply:
            print()
            print("DRY-RUN: no se ha escrito nada. Repite con --apply.")
            await engine.dispose()
            return 0

        now = datetime.now(UTC)
        for r in emparejadas:
            pareja_id = r.transfer_pair_id
            await unlink(db, job.user_id, r.id)
            if pareja_id is not None:
                pareja = await db.get(Transaction, pareja_id)
                if pareja is not None and pareja.deleted_at is None:
                    pareja.deleted_at = now
        for r in espejos:
            r.absorbed_as_mirror = False
        for r in vivas:
            r.deleted_at = now
        await db.commit()

        print()
        print(f"APLICADO: {len(vivas)} filas a la papelera, {len(emparejadas)} enlaces deshechos.")
        print("Ahora reimporta el PDF eligiendo la cuenta de la tarjeta.")

    await engine.dispose()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True, help="UUID del import_job a deshacer")
    parser.add_argument("--apply", action="store_true", help="escribe (por defecto: dry-run)")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(uuid.UUID(args.job), args.apply)))


if __name__ == "__main__":
    main()
