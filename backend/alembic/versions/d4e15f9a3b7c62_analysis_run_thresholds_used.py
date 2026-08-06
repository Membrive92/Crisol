"""PHASE-44.9 — `analysis_runs.thresholds_used`: los cortes EFECTIVOS del run.

Sin esta columna, los umbrales con los que se juzgó un análisis pasado son
**irrecuperables**, así que la pantalla no puede decir «frente a qué corte» está
en ámbar una métrica:

- `scoring_thresholds` tiene la unique `(sector, accounting_std, metric_key)`
  sin versión ni vigencia, y el seed **muta la fila existente in situ**
  (`thresholds/service.py:104-110`): la calibración de ayer se pierde.
- `thresholds_version` es un SHA-256 (`thresholds/service.py:58-78`). Sirve para
  DETECTAR que dos runs usaron cortes distintos; jamás para reconstruirlos.
- `load_thresholds` fusiona BD **sobre** los defaults del engine, así que ni
  leyendo la tabla entera se reproduce el juego que se aplicó.

Va en columna propia y no colgando de `verdict` porque son dos
responsabilidades distintas: `verdict` es el dictamen, esto es la vara de medir
([`lessons.md`, PHASE-23.1] — no mezclar dos cosas ortogonales en el mismo
contenedor).

Aditiva y reversible. Los runs anteriores quedan con `{}`: no se inventa su
calibración retroactivamente, y la UI lo declara en vez de fingirla.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d4e15f9a3b7c62"
down_revision: str | None = "cc3d69e1f4a8b2"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "analysis_runs",
        sa.Column(
            "thresholds_used",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("analysis_runs", "thresholds_used")
