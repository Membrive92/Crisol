"""Normaliza las fechas de movimiento a medianoche UTC (PHASE-47).

**Qué arregla.** `transactions.occurred_at` es `TIMESTAMPTZ`, pero lo que se
guarda ahí es una fecha CIVIL: el día que imprime el banco. Hasta PHASE-47 el
parser del import devolvía un `datetime` naive, y asyncpg codifica un naive con
`astimezone(utc)` — que sobre un naive asume la zona **del proceso**. Con el
backend corriendo en Europe/Madrid, «13/02/2026» se persistía como
`2026-02-12T23:00:00Z` (22:00 en horario de verano).

La app formatea en hora local, así que en pantalla el día salía bien; pero los
filtros de rango se construyen en UTC, de modo que un movimiento del día 13
quedaba FUERA de un rango que empieza el día 13. Con el ciclo del usuario en
D=13 eso son 3 movimientos de febrero y 6 de marzo en el ciclo equivocado, y
14 filas cambiando de mes natural — entre ellas una transferencia de 4.267,47 €
que contaba en marzo siendo del 1 de abril.

**Cómo decide la fecha civil, y por qué es seguro.** No se fía de la hora: usa
un testigo. El `import_hash` de cada fila se calculó con la fecha civil que el
parser leyó del extracto (`user|amount|currency|fecha|desc`), así que
recomputarlo con la fecha candidata y compararlo con el almacenado PRUEBA que la
candidata es la que venía en el fichero. Si no cuadra, la fila no se toca y se
reporta. Las filas sin `import_hash` (manuales, tickets) no tienen testigo: para
ellas se aplica la regla de la hora —22:00Z y 23:00Z son las dos medianoches de
Madrid— y se listan aparte para que se puedan revisar a ojo.

**Lo que NO toca**, y es deliberado:

- Las filas que ya están a medianoche UTC. Hay 21 de ellas con `source=IMPORT`,
  y no es casualidad: `update_transaction` hace `setattr` con lo que manda el
  formulario, que emite `T00:00:00Z`, así que editar y guardar una fila ya la
  arreglaba. Volver a desplazarlas las rompería.
- Los `import_hash`. Desde PHASE-47 el hash se calcula sobre la fecha SIN
  sufijo de zona, así que el valor no cambia al mover el timestamp — verificado
  contra filas reales. Si este script tuviera que rehashear, sería señal de que
  esa parte se ha revertido.
- Los saldos. `get_balances_for_user` no lleva cota temporal: la Σ es
  independiente del timestamp. Aun así, pasa `make audit-balances` después.

**Uso**::

    python -m scripts.normalize_civil_dates                # dry-run (default)
    python -m scripts.normalize_civil_dates --apply
    python -m scripts.normalize_civil_dates --user a@b.com --apply
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.main  # noqa: F401  (efecto lateral: registra todos los modelos)
from app.core.config import settings
from app.modules.personal_finance.debt.installments_model import LiabilityInstallment
from app.modules.personal_finance.imports.service import _compute_hash
from app.modules.personal_finance.transactions.models import Transaction
from app.modules.users.models import User

# Las dos medianoches de Madrid vistas desde UTC: CET (UTC+1) en invierno y
# CEST (UTC+2) en verano. Son la firma inequívoca del bug — nadie escribe las
# 22:00 a mano.
HORAS_DESPLAZADAS = {22: 2, 23: 1}


def fecha_civil_candidata(occurred_at: datetime) -> datetime | None:
    """Medianoche UTC del día civil que representa este instante, o `None`.

    `None` cuando la fila no lleva la firma del desplazamiento: o ya está a
    medianoche UTC, o tiene una hora que este script no sabe interpretar y
    prefiere no inventar.
    """
    en_utc = occurred_at.astimezone(UTC)
    if en_utc.hour == 0 and en_utc.minute == 0 and en_utc.second == 0:
        return None  # ya correcta
    horas = HORAS_DESPLAZADAS.get(en_utc.hour)
    if horas is None or en_utc.minute != 0 or en_utc.second != 0:
        return None  # hora que no es una medianoche de Madrid
    return (en_utc + timedelta(hours=horas)).replace(hour=0, minute=0, second=0, microsecond=0)


def _hash_de(tx: Transaction, occurred_at: datetime, occurrence: int) -> str:
    return _compute_hash(
        user_id=tx.user_id,
        amount=tx.amount,
        currency=tx.currency,
        occurred_at=occurred_at,
        description=tx.description,
        occurrence=occurrence,
    )


def confirma_el_testigo(tx: Transaction, candidata: datetime) -> bool:
    """¿El `import_hash` almacenado se reproduce con esta fecha civil?

    El ordinal (`occurrence`) no se persiste: se probó 0, 1, 2… en el import
    para desempatar filas idénticas del mismo lote, así que aquí se prueban los
    primeros. Si ninguno reproduce el hash, la candidata no es la fecha que
    venía en el fichero y la fila no se toca.
    """
    if tx.import_hash is None:
        return False
    return any(_hash_de(tx, candidata, n) == tx.import_hash for n in range(0, 12))


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="escribe (por defecto: dry-run)")
    parser.add_argument("--user", default=None, help="limitar a un email")
    parser.add_argument("--verbose", action="store_true", help="una línea por fila")
    args = parser.parse_args()

    engine = create_async_engine(settings.database_url, future=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    movidas = 0
    sin_testigo: list[str] = []
    intactas: Counter[str] = Counter()
    cuotas_movidas = 0

    async with session_factory() as db:
        q = select(Transaction)
        if args.user:
            q = q.join(User, User.id == Transaction.user_id).where(User.email == args.user)
        filas = list((await db.execute(q)).scalars().all())

        nuevas_por_tx: dict[object, datetime] = {}
        for tx in filas:
            candidata = fecha_civil_candidata(tx.occurred_at)
            if candidata is None:
                en_utc = tx.occurred_at.astimezone(UTC)
                intactas[f"{en_utc:%H:%M:%S}"] += 1
                continue
            probada = confirma_el_testigo(tx, candidata)
            if not probada and tx.import_hash is not None:
                sin_testigo.append(
                    f"  ! {tx.occurred_at:%Y-%m-%d %H:%M}Z {tx.amount:>9} "
                    f"«{(tx.description or '')[:34]}» — el hash no cuadra, NO se toca"
                )
                continue
            if args.verbose:
                origen = "hash" if probada else "hora"
                print(
                    f"  {tx.occurred_at:%Y-%m-%d %H:%M}Z -> {candidata:%Y-%m-%d} 00:00Z "
                    f"[{origen}] {tx.amount:>9} «{(tx.description or '')[:30]}»"
                )
            if not probada:
                sin_testigo.append(
                    f"  ~ {tx.occurred_at:%Y-%m-%d %H:%M}Z {tx.amount:>9} "
                    f"«{(tx.description or '')[:34]}» — sin hash, movida por la hora"
                )
            nuevas_por_tx[tx.id] = candidata
            movidas += 1
            if args.apply:
                tx.occurred_at = candidata

        # `liability_installments.paid_at` copia el `occurred_at` del cargo que
        # marcó la cuota (transfers/service.py), así que hereda el desfase. Se
        # re-deriva del movimiento, que es su fuente: no se recalcula a ojo.
        cuotas = list(
            (
                await db.execute(
                    select(LiabilityInstallment).where(LiabilityInstallment.paid_at.is_not(None))
                )
            )
            .scalars()
            .all()
        )
        for cuota in cuotas:
            if cuota.paid_at is None:
                continue
            # Preferencia: re-derivar del movimiento que la marcó, que es su
            # fuente. Si el enlace se perdió —10 cuotas de julio están así, sin
            # `paid_transaction_id` pese a llevar el instante de su cargo—, se
            # cae a la misma regla de la hora que las transacciones. El ancla
            # sintética de PHASE-36 (`2000-01-01T00:00Z`) no entra por ninguna
            # de las dos vías: ya está a medianoche.
            nueva = nuevas_por_tx.get(cuota.paid_transaction_id)
            if nueva is None:
                nueva = fecha_civil_candidata(cuota.paid_at)
            if nueva is None or cuota.paid_at.astimezone(UTC) == nueva:
                continue
            cuotas_movidas += 1
            if args.apply:
                cuota.paid_at = nueva

        if args.apply:
            await db.commit()

    print()
    print(f"Filas examinadas ......... {len(filas)}")
    print(f"Fechas normalizadas ...... {movidas}")
    print(f"Cuotas re-derivadas ...... {cuotas_movidas}  (liability_installments.paid_at)")
    if intactas:
        detalle = ", ".join(f"{n}×{h}" for h, n in sorted(intactas.items(), key=lambda x: -x[1]))
        print(f"Intactas ................. {sum(intactas.values())}  ({detalle})")
    if sin_testigo:
        print(f"\nRevisables ({len(sin_testigo)}):")
        for linea in sin_testigo[:40]:
            print(linea)
        if len(sin_testigo) > 40:
            print(f"  … y {len(sin_testigo) - 40} más")
    print()
    print("APLICADO." if args.apply else "DRY-RUN: no se ha escrito nada. Repite con --apply.")
    if args.apply:
        print("Siguiente paso obligatorio: `make audit-balances` (los saldos no deberían moverse).")
    await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
