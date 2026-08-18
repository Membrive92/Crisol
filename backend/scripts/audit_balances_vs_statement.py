"""Auditoría: el saldo que calcula la app vs. el que dice el extracto del banco.

**Por qué existe.** El desfase de 700,26 € de BBVA (PHASE-47.E) estuvo vivo días
sin que nada lo dijera: los saldos se miran de uno en uno y contra la intuición,
no contra una referencia. Pero la referencia existe desde PHASE-39 —
`accounts.anchored_statement_balance` guarda lo que el propio banco imprimió — y
nadie la consultaba después de anclarla. Este script la consulta.

Ejecuta la FUNCIÓN REAL (`get_balances_for_user`) en vez de reproducir la
expresión de signo en SQL: tiene carve-outs, y reimplementarla a mano es
exactamente como se llega a un diagnóstico equivocado con aritmética plausible
(lección [PHASE-44.12]).

**Qué significa una diferencia.** El ancla se fija al confirmar una importación,
así que en ese instante la diferencia es 0 por construcción. Si más tarde no lo
es, algo movió el saldo DESPUÉS de anclarlo: una conversión a deuda, un borrado,
una recategorización. No dice cuál — dice que lo mires.

Uso:
    cd backend && .venv/Scripts/python.exe -m scripts.audit_balances_vs_statement
    ... --email otro@ejemplo.com     # por defecto, todos los usuarios

Sale con código 1 si alguna cuenta anclada diverge, para poder encadenarlo.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.main  # noqa: F401  (efecto lateral: registra todos los modelos)
from app.core.config import settings
from app.modules.personal_finance.accounts.models import Account, AccountNature
from app.modules.personal_finance.accounts.repository import (
    find_statement_seams,
    get_balances_for_user,
)
from app.modules.personal_finance.debt.installments_repository import (
    installments_by_account,
    resolve_liability_outstanding,
)
from app.modules.users.models import User

#: Por debajo de un céntimo no hay nada que auditar: es ruido de redondeo.
TOLERANCE = Decimal("0.01")


async def audit(email: str | None) -> int:
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    divergent = 0
    try:
        async with session_factory() as db:
            query = select(User)
            if email is not None:
                query = query.where(User.email == email)
            users = (await db.execute(query)).scalars().all()
            if not users:
                print("No hay usuarios que auditar.")
                return 0

            for user in users:
                accounts = (
                    (await db.execute(select(Account).where(Account.user_id == user.id)))
                    .scalars()
                    .all()
                )
                if not accounts:
                    # Una base de desarrollo acumula usuarios de pruebas sin
                    # cuentas. Listarlos vacíos entierra el único hallazgo real,
                    # y un informe que hay que rebuscar se deja de leer.
                    continue
                balances = await get_balances_for_user(db, user.id)
                seams = await find_statement_seams(db, user.id)
                # PHASE-36: el saldo vivo de un pasivo CON cuadro lo manda el
                # cuadro, no sus movimientos. Sin esto el informe enseñaba 0 en
                # una deuda de 700,26 € y parecía un descuadre de la app cuando
                # el descuadre era de este script.
                insts = await installments_by_account(
                    db, user.id, [a.id for a in accounts if a.nature == AccountNature.LIABILITY]
                )
                print(f"\n{user.email}")
                print(f"  {'cuenta':<30} {'app':>12} {'extracto':>12} {'diferencia':>12}")
                print(f"  {'-' * 68}")
                for account in sorted(accounts, key=lambda a: (a.nature.value, a.name)):
                    movement = balances.get(account.id, Decimal(0))
                    app_balance = (account.opening_balance or Decimal(0)) + movement
                    if account.nature == AccountNature.LIABILITY:
                        resolved = resolve_liability_outstanding(
                            opening_balance=account.opening_balance,
                            movements_balance=movement,
                            installments=insts.get(account.id, []),
                        )
                        app_balance = resolved.value
                    anchor = account.anchored_statement_balance
                    if anchor is None:
                        # Un pasivo no tiene extracto con saldo corriente, y una
                        # cuenta sin importar nunca tampoco. No es un hallazgo.
                        print(f"  {account.name:<30} {app_balance:>12} {'sin ancla':>12} {'':>12}")
                        continue
                    difference = app_balance - anchor
                    mark = "  <-- MIRA" if abs(difference) >= TOLERANCE else ""
                    if abs(difference) >= TOLERANCE:
                        divergent += 1
                    print(
                        f"  {account.name:<30} {app_balance:>12} {anchor:>12} "
                        f"{difference:>12}{mark}"
                    )
                for account in sorted(accounts, key=lambda a: a.name):
                    for seam in seams.get(account.id, []):
                        divergent += 1
                        print(
                            f"  HUECO  {account.name}: entre {seam.after.date()} y "
                            f"{seam.before.date()} faltan movimientos por {seam.amount}"
                        )
    finally:
        await engine.dispose()

    print()
    if divergent:
        print(
            f"{divergent} hallazgo(s). Una DIFERENCIA significa que algo movio el saldo "
            "despues de anclarlo; un HUECO, que falta por importar un tramo de extracto."
        )
        return 1
    print("Todas las cuentas cuadran con su extracto y no falta ningun tramo.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", default=None, help="auditar sólo a este usuario")
    args = parser.parse_args()
    sys.exit(asyncio.run(audit(args.email)))


if __name__ == "__main__":
    main()
