"""Seeds del módulo currency.

Datos públicos (tasas ECB) embebidos en el repo para que la app
arranque utilizable en hosts sin red. La función `load_snapshot()`
parsea el CSV y devuelve una lista de dicts lista para
`bulk_insert` desde Alembic o tests.
"""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path
from typing import TypedDict


class SnapshotRow(TypedDict):
    rate_date: str  # ISO YYYY-MM-DD; la migración la convierte a date
    base: str
    quote: str
    rate: Decimal
    source: str


_CSV_PATH = Path(__file__).parent / "rates.csv"


def load_snapshot() -> list[SnapshotRow]:
    """Lee `rates.csv` y devuelve las filas tipadas.

    Las líneas vacías y las que empiezan por `#` se ignoran (permiten
    comentarios in-line en el CSV).
    """
    rows: list[SnapshotRow] = []
    with _CSV_PATH.open(encoding="utf-8") as fh:
        # Saltamos líneas de comentario antes de pasarlo al DictReader.
        cleaned = (line for line in fh if line.strip() and not line.lstrip().startswith("#"))
        reader = csv.DictReader(cleaned)
        for raw in reader:
            rows.append(
                {
                    "rate_date": raw["rate_date"],
                    "base": raw["base"].strip().upper(),
                    "quote": raw["quote"].strip().upper(),
                    "rate": Decimal(raw["rate"]),
                    "source": "snapshot",
                }
            )
    return rows
