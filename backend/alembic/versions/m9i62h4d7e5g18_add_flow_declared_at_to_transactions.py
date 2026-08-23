"""Una declaración manual sobrevive a una reimportación — `transactions.flow_declared_at`

Reimportar un extracto BORRA las filas viejas y crea otras. Con las viejas se
van sus declaraciones a nivel de fila. Medido en datos reales el 2026-08-18: la
reimportación de julio se llevó los cuatro `Adeudo mensual` que el usuario había
declarado GASTO (1.099,64 € de liquidaciones anticipadas), que renacieron
neutros, y el resultado del mes pasó de −253,17 a +398,87 € **sin que nadie lo
decidiera**.

La fila reimportada llega con EL MISMO `import_hash` que la borrada (se compone
de usuario + importe + fecha + descripción), así que el import puede ir a
buscarla a la papelera y recuperar lo que el usuario había declarado. Lo que no
podía es distinguir una DECLARACIÓN de una conjetura del clasificador: las dos
viven en la misma columna `flow` y ninguna lleva firma.

Esta columna es esa firma. `NULL` = la dirección la puso el sistema; con valor,
la declaró el usuario y ese día. No es un booleano a propósito —la fecha dice
además cuándo— y no lleva default: `NULL` *es* el estado correcto de todo lo ya
existente, porque de esas filas no consta ninguna declaración. Un
`DEFAULT false` afirmaría lo mismo, pero un `DEFAULT true` habría afirmado que
el usuario declaró a mano 484 filas que en realidad importó (lección
PHASE-44.11: un valor por defecto es una afirmación dormida).

**Sin backfill, y eso tiene consecuencia**: las declaraciones que el usuario ya
hizo a mano ANTES de esta migración no llevan firma, así que una reimportación
todavía se las llevaría. No hay forma honesta de recuperarlas —deducirlas
comparando con el clasificador de hoy es justo la conjetura que esta columna
existe para evitar—. A partir de aquí, sí.

Revision ID: m9i62h4d7e5g18
Revises: l8h51g3c6d4f07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m9i62h4d7e5g18"
down_revision: str | None = "l8h51g3c6d4f07"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("flow_declared_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transactions", "flow_declared_at")
