"""scoring_thresholds: por qué una vara no aplica

Aditiva y reversible: una columna TEXT NULL.

Sin ella, un umbral apagado (`applies=false`) llega a la pantalla como un número
gris sin explicación, que se lee igual que «no se ha podido calcular» — y manda
el diagnóstico a las cuentas de la empresa cuando lo que pasa es que la vara no
sirve para ese sector. La razón la escribe el engine (`sector_profiles`); esta
columna es sólo donde se guarda para que viaje en `thresholds_used`.

**No hay backfill**: las filas existentes quedan con `NULL` hasta que la
sincronización del arranque las reescriba desde la calibración del engine
(`sync_thresholds`, PHASE-44.21). Inventar aquí una razón para 1.500 filas sería
escribir a mano lo que el motor sabe derivar.

Revision ID: g3c95b7d2e8f41
Revises: f2b84a6c1d9e73
Create Date: 2026-08-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "g3c95b7d2e8f41"
down_revision: str | None = "f2b84a6c1d9e73"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "scoring_thresholds",
        sa.Column("not_applicable_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("scoring_thresholds", "not_applicable_reason")
