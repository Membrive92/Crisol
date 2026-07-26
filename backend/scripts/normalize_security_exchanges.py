"""Repunta los `securities.exchange` legacy al vocabulario de plazas.

PHASE-44.8 E1. El frontend escribía `'US'` —un país, no un mercado— en una
columna cuya restricción única es `(ticker, exchange)`. El código ya no lo
permite (`catalog/venues.normalize_venue`), pero las filas creadas antes siguen
con el valor viejo.

Va en un script y **no** en una migración a propósito: una migración reproduce
los datos, no los corrige como efecto colateral (lección PHASE-34). Así el
arreglo es auditable, se puede ensayar y se ejecuta cuando su dueño quiere.

Uso:

    # Ensayo: enseña qué haría y no escribe nada (por defecto)
    .venv/Scripts/python.exe scripts/normalize_security_exchanges.py

    # Aplicar de verdad
    .venv/Scripts/python.exe scripts/normalize_security_exchanges.py --apply

Es idempotente: una segunda pasada no encuentra nada que hacer. Y aborta la fila
—sin tocarla— si el destino ya existe, porque fusionar dos `Security` arrastra
ingestas, runs y lotes de cartera: eso no lo decide un script.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.modules.investment.catalog.models import Security
from app.modules.investment.catalog.venues import UNKNOWN, is_known_venue, normalize_venue

#: Plazas reales de los emisores que se sabe que están mal por el bug original.
#: Sólo se usa cuando la normalización no puede deducir nada (`'US'` → UNKNOWN):
#: es preferible la plaza verdadera a un "no lo sé" cuando consta.
_KNOWN_LISTINGS: dict[str, str] = {
    "0000063908": "NYSE",  # McDonald's Corp
    "0000200406": "NYSE",  # Johnson & Johnson
}


def _target_venue(security: Security) -> str:
    """A qué plaza debería moverse esta fila."""
    normalized = normalize_venue(security.exchange)
    if normalized != UNKNOWN:
        return normalized
    if security.cik and security.cik in _KNOWN_LISTINGS:
        return _KNOWN_LISTINGS[security.cik]
    return UNKNOWN


async def run(*, apply: bool) -> int:
    session: AsyncSession
    async with SessionLocal() as session:
        rows = list((await session.execute(select(Security).order_by(Security.ticker))).scalars())
        by_key = {(s.ticker, s.exchange) for s in rows}

        pending: list[tuple[Security, str]] = []
        for security in rows:
            target = _target_venue(security)
            if target == security.exchange:
                continue
            if (security.ticker, target) in by_key:
                print(
                    f"  ! {security.ticker}: {security.exchange} -> {target} OMITIDA "
                    f"— ya existe esa fila. Fusionarlas arrastra ingestas, runs y "
                    f"lotes: hay que decidirlo a mano."
                )
                continue
            pending.append((security, target))

        if not pending:
            print("Nada que normalizar: todas las plazas están en el vocabulario.")
            return 0

        print(f"{len(pending)} fila(s) a normalizar:")
        for security, target in pending:
            marca = "" if is_known_venue(target) else "  (queda como desconocida)"
            print(f"  - {security.ticker:8} {security.exchange:8} -> {target}{marca}")

        if not apply:
            print("\nEnsayo: no se ha escrito nada. Repite con --apply para aplicarlo.")
            return 0

        for security, target in pending:
            security.exchange = target
        await session.commit()
        print(f"\nAplicado: {len(pending)} fila(s) actualizadas.")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Escribe los cambios. Sin este flag sólo enseña qué haría.",
    )
    args = parser.parse_args()
    return asyncio.run(run(apply=args.apply))


if __name__ == "__main__":
    sys.exit(main())
