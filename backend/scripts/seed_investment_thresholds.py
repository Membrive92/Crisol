"""Sincroniza `scoring_thresholds` con la calibración del engine (PHASE-44.7).

Idempotente: se puede correr las veces que haga falta. El arranque de la app ya
lo hace, así que este script es para forzarlo a mano tras cambiar la calibración
sectorial (`analysis/engine/sector_profiles.py`) sin reiniciar el servidor.

Uso:
    .venv/Scripts/python.exe scripts/seed_investment_thresholds.py
"""

from __future__ import annotations

import asyncio

from app.core.database import SessionLocal
from app.modules.investment.thresholds.service import sync_thresholds


async def main() -> None:
    async with SessionLocal() as db:
        outcome = await sync_thresholds(db)
        await db.commit()
    print(
        f"scoring_thresholds sincronizados: {outcome.inserted} filas nuevas, "
        f"{outcome.updated} actualizadas"
    )


if __name__ == "__main__":
    asyncio.run(main())
