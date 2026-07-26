"""Siembra `scoring_thresholds` (PHASE-44.7).

Idempotente: se puede correr las veces que haga falta. El arranque de la app ya
llama a `seed_if_empty`, así que este script es para sembrar/reforzar a mano
(p. ej. tras cambiar la calibración en el catálogo del engine).

Uso:
    .venv/Scripts/python.exe scripts/seed_investment_thresholds.py
"""

from __future__ import annotations

import asyncio

from app.core.database import SessionLocal
from app.modules.investment.thresholds.service import seed_scoring_thresholds


async def main() -> None:
    async with SessionLocal() as db:
        inserted = await seed_scoring_thresholds(db)
        await db.commit()
    print(f"scoring_thresholds sembrados: {inserted} filas nuevas (idempotente)")


if __name__ == "__main__":
    asyncio.run(main())
