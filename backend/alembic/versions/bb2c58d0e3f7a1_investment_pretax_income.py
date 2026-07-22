"""PHASE-44.6 — `pretax_income`, la 49ª partida canónica.

El cruzado con EDGAR (MCD/O/JNJ) mostró que `OperatingIncomeLoss` no es fiable
en XBRL: JNJ dejó de publicarlo en 2015 y los REIT no tienen línea de resultado
operativo. El EBIT hay que derivarlo del resultado antes de impuestos, y
reconstruir ese resultado como `net_income + taxes` ignora los minoritarios y
las actividades discontinuadas (en Realty Income, 11,2 M$ de diferencia).

Con el pretax REPORTADO como partida propia la derivación parte de un dato
sourced y la bandera `ebt_divergence` vuelve a comparar dos fuentes
independientes en vez de una identidad tautológica.

Aditiva y reversible: una columna nullable (hueco ≠ 0, §4.5).

Revision ID: bb2c58d0e3f7a1
Revises: aa1b47c9d2e6f0
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "bb2c58d0e3f7a1"
down_revision: str | None = "aa1b47c9d2e6f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "financial_statements"
_COLUMN = "pretax_income"


def upgrade() -> None:
    op.add_column(_TABLE, sa.Column(_COLUMN, sa.Numeric(20, 4), nullable=True))


def downgrade() -> None:
    op.drop_column(_TABLE, _COLUMN)
