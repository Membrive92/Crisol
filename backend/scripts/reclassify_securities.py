"""Data-fix: repunta el sector y los flags de los valores ya en el catalogo.

**Por que existe.** Desde PHASE-44.21 el sector elige los UMBRALES con los que se
juzga una empresa, y `securities.sector` se decidia UNA vez, al dar de alta el
valor. Corregir el mapeo SIC -> sector (`catalog/sic_mapping.py`) alcanzaba
entonces a las altas futuras y nunca a lo que ya estaba en el catalogo, que es
justo lo que se esta analizando. Es el mismo defecto que el sembrado
solo-insercion de los umbrales, en otra tabla.

`resolve_security` ya lo refresca cuando vuelve a resolver un valor, pero hay un
camino rapido deliberado: un valor con analisis disponible NO se re-resuelve (un
emisor no deja de publicar cuentas de un dia para otro, y no vale la pena pagar
una peticion a la SEC en cada alta). Este script es la salida para ese caso.

**Por que necesita red.** El SIC no se persiste: vive en el perfil del emisor en
EDGAR. Reclasificar exige volver a preguntarlo, aunque la cache del adapter
absorbe las repeticiones.

Uso:
    python -m scripts.reclassify_securities            # dry-run: solo informa
    python -m scripts.reclassify_securities --apply    # escribe

Solo toca valores CON CIK: los del directorio europeo no tienen SIC y su sector
es `unknown` por construccion, no por haberse quedado atras.
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.main  # noqa: F401  (efecto lateral: registra los modelos en el metadata)
from app.core.config import settings
from app.modules.investment.catalog.models import Security
from app.modules.investment.catalog.sic_mapping import sic_to_sector
from app.modules.investment.fundamentals.adapters.factory import build_edgar_adapter


async def main(apply: bool) -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    adapter = build_edgar_adapter()
    changed = 0
    checked = 0

    async with factory() as db:
        securities = list(
            (await db.execute(select(Security).where(Security.cik.is_not(None)))).scalars().all()
        )
        for security in securities:
            checked += 1
            try:
                identity = await adapter.resolve(security.ticker)
            except Exception as error:  # un valor que falle no debe parar al resto
                print(f"  !! {security.ticker}: no se pudo resolver ({error})")
                continue

            target = (sic_to_sector(identity.sic), identity.is_financial, identity.is_reit)
            current = (security.sector, security.is_financial, security.is_reit)
            if current == target:
                continue

            changed += 1
            print(
                f"  {security.ticker}: {current[0]} -> {target[0]}"
                f" | financiera {current[1]} -> {target[1]}"
                f" | reit {current[2]} -> {target[2]}"
            )
            if apply:
                security.sector, security.is_financial, security.is_reit = target

        if apply and changed:
            await db.commit()

    await engine.dispose()
    verbo = "actualizados" if apply else "por actualizar (dry-run)"
    print(f"\n{checked} valores comprobados, {changed} {verbo}.")
    if changed and apply:
        print("Reejecuta los analisis afectados: el sector elige los umbrales.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="escribe los cambios")
    args = parser.parse_args()
    asyncio.run(main(apply=args.apply))
