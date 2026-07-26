"""PHASE-44.8 — `securities.analysis_status`: la evidencia de si algo se puede analizar.

Hasta ahora la pregunta «¿se puede analizar este valor?» se contestaba con
`cik is not None`, y ese predicado es falso: SPY (CIK 0000884394) y QQQ
(0001067839) tienen CIK y **no presentan 10-K** —verificado en sus `submissions`:
sólo 24F-2NT y N-CSR—, así que salían marcados como analizables. Al elegirlos, la
ingesta fallaba y el análisis contestaba «lanza la ingesta primero»: un callejón
en el que el mensaje manda a hacer lo que acaba de fallar.

No se puede resolver sin persistir: distinguir «tiene CIK pero no presenta
anuales» de «presenta 20-F con IFRS» exige contar filings, o sea red, y el
buscador tiene que responder sin salir de la máquina. La columna guarda esa
evidencia una vez.

`String(16)` y no un enum nativo a propósito: el conjunto de estados va a crecer
y un `ALTER TYPE ... ADD VALUE` no se deshace en un `downgrade` limpio.

Nullable = «no comprobado», que es lo que son todas las filas existentes. Nadie
las reinterpreta: sin valor, la regla responde lo mismo que antes (ADR-0008).

Aditiva y reversible.

Revision ID: cc3d69e1f4a8b2
Revises: bb2c58d0e3f7a1
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "cc3d69e1f4a8b2"
down_revision: str | None = "bb2c58d0e3f7a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "securities"
_COLUMN = "analysis_status"


def upgrade() -> None:
    op.add_column(_TABLE, sa.Column(_COLUMN, sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column(_TABLE, _COLUMN)
