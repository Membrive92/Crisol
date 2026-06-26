"""AUDIT — sql-no-zero-rate-guard (c): CHECK (rate > 0) en exchange_rates.

La conversión de importes compone `amount / from_rate` (ver
`dashboard/conversion.py` y `currency/service.convert`). Una tasa cero o
negativa provoca división por cero (HTTP 500) o invierte el signo del
importe convertido — ambos son corrupciones silenciosas del dinero.

Esta migración añade la invariante a nivel de BD para que ninguna fila
inválida llegue a persistirse, sea cual sea la vía de inserción (cliente
HTTP, seed, fixes manuales). Es la última línea de defensa tras la
validación en `client.fetch_rates` (a) y el guard en SQL (b).

`NOT VALID` + `VALIDATE` por separado evita un lock largo sobre la tabla
en producción y, si existieran filas no-positivas previas, la validación
fallaría señalando el problema en vez de romper el ADD silenciosamente.
Como la tabla solo contiene tasas del ECB (siempre positivas) no se
esperan filas inválidas; el patrón es defensivo.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "x1n36p8ml0o9n5"
down_revision: str | None = "w0m25o7lk9n8m4"
branch_labels: str | None = None
depends_on: str | None = None

_CONSTRAINT_NAME = "ck_exchange_rates_rate_positive"


def upgrade() -> None:
    bind = op.get_bind()
    # Idempotente: si una corrida previa lo dejó a medias, no rompemos.
    bind.execute(
        sa.text(
            "ALTER TABLE exchange_rates "
            f"DROP CONSTRAINT IF EXISTS {_CONSTRAINT_NAME};"
        )
    )
    bind.execute(
        sa.text(
            "ALTER TABLE exchange_rates "
            f"ADD CONSTRAINT {_CONSTRAINT_NAME} CHECK (rate > 0) NOT VALID;"
        )
    )
    bind.execute(
        sa.text(
            "ALTER TABLE exchange_rates "
            f"VALIDATE CONSTRAINT {_CONSTRAINT_NAME};"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "ALTER TABLE exchange_rates "
            f"DROP CONSTRAINT IF EXISTS {_CONSTRAINT_NAME};"
        )
    )
