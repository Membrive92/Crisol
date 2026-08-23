"""El mes lo define el usuario — `users.cycle_start_day`

El usuario cobra los días 14-15 y su ciclo de pagos vive en esa ventana. El mes
natural reparte la nómina y el recibo de la tarjeta en períodos distintos, así
que da una foto 3-4× distinta del MISMO dinero (medido contra extractos reales
el 2026-08-18: ≈ +1.200 € con la ventana 1-ago→15-ago frente a ≈ +300/600 € con
la ventana nómina-a-nómina 14-jul→15-ago). Esta columna guarda el día en que
EMPIEZA el mes del usuario a efectos de **presentación**.

Presentación, y sólo presentación: no toca `flow`, ni saldos, ni el ancla del
saldo de extracto, ni el cuadro de amortización, ni el modelo del recibo
aplazado. Es la familia de lecciones PHASE-34/37/38 — la fuente de verdad del
dinero no se mueve por una cuestión de etiquetas. El invariante está escrito
como test (`tests/test_user_cycle.py::test_el_ciclo_no_mueve_ni_un_centimo`),
no como comentario, porque un comentario no se recalcula.

**Sin backfill, y sin default numérico.** `NULL` no es un hueco por rellenar:
*es* el estado correcto de todo el mundo hoy (mes natural, comportamiento
actual). Un `DEFAULT 1` afirmaría que el usuario declaró que su mes empieza el
día 1 — falso — y esa afirmación dormida despertaría el día que alguien empiece
a leer la columna, indistinguible de un dato que puso una persona (lección
PHASE-44.11).

El rango 1–28 lo fija un CHECK en la BD, última línea de defensa tras el
`Field(ge=1, le=28)` del schema Pydantic, valga cual valga la vía de escritura.
Los días 29-31 quedan fuera **a propósito**: con `D ≤ 28` no hay clamping de fin
de mes jamás, y el clamp de febrero convierte el ciclo en una charca de bugs.

Revision ID: l8h51g3c6d4f07
Revises: k7g40f2b5c3e96
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "l8h51g3c6d4f07"
down_revision: str | None = "k7g40f2b5c3e96"
branch_labels: str | None = None
depends_on: str | None = None

_CONSTRAINT_NAME = "ck_users_cycle_start_day_range"


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("cycle_start_day", sa.SmallInteger(), nullable=True),
    )
    bind = op.get_bind()
    # Idempotente: si una corrida previa lo dejó a medias, no rompemos. No hace
    # falta `NOT VALID` + `VALIDATE` como en `exchange_rates`: la columna acaba
    # de nacer, así que todas las filas están a NULL y no puede haber ninguna
    # que viole el CHECK.
    bind.execute(sa.text(f"ALTER TABLE users DROP CONSTRAINT IF EXISTS {_CONSTRAINT_NAME};"))
    bind.execute(
        sa.text(
            f"ALTER TABLE users ADD CONSTRAINT {_CONSTRAINT_NAME} "
            "CHECK (cycle_start_day BETWEEN 1 AND 28);"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    # `DROP COLUMN` ya se llevaría el CHECK por delante; se hace explícito para
    # que `upgrade` y `downgrade` sean simétricos paso a paso.
    bind.execute(sa.text(f"ALTER TABLE users DROP CONSTRAINT IF EXISTS {_CONSTRAINT_NAME};"))
    op.drop_column("users", "cycle_start_day")
