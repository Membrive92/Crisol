"""import_jobs: huella de la cabecera del fichero

Aditiva y reversible: una columna nullable.

Identifica el FORMATO del fichero (qué producto del banco lo exportó) para poder
avisar cuando uno con la cabecera de otra cuenta se está importando a ésta. En
julio de 2026 el extracto de la tarjeta entró en la cuenta del banco sin un solo
error: 19 filas OK. El fallo sólo asomó comparando el recuento de compras entre
meses.

Sin backfill AQUÍ: la huella de los jobs históricos se puede derivar de su
`preview_payload`, pero eso es corregir datos y una migración reproduce, no
corrige ([PHASE-34]). Va en `scripts/backfill_header_fingerprint.py`, con
`--dry-run` y `--apply`. No es opcional: sin él la señal nace ciega y no detecta
nada hasta que cada cuenta tenga un import posterior a 47.A — o sea, no habría
cazado julio.

Revision ID: j6f39e1a4b2d85
Revises: i5e28d0f3a1c74
Create Date: 2026-08-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "j6f39e1a4b2d85"
down_revision: str | None = "i5e28d0f3a1c74"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "import_jobs",
        sa.Column("header_fingerprint", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("import_jobs", "header_fingerprint")
