"""PHASE-44.14 — `listing_directory`: directorio oficial de valores UE/UK (ADR-0010).

Tabla **GLOBAL** (sin `user_id`, extiende ADR-0007): el universo de instrumentos
admitidos a negociación que publican ESMA (UE/EEA) y la FCA (UK) en sus ficheros
FIRDS. Es la capa de **identidad** del buscador multi-mercado — qué valores
existen, con qué nombre, en qué plaza y en qué divisa — con identificadores
registrales (ISIN, MIC, LEI, CFI), sin convención propietaria de ningún
proveedor de precios.

La PK es `(isin, mic)`: un instrumento por plaza. El MIC almacenado es el
**OPERATIVO** (XETR, no el segmento XETA con el que reporta FIRDS): la
normalización segmento→operativo la hace el seed contra el registro ISO 10383,
para que esta columna hable el mismo vocabulario que `securities.exchange` y que
el mapa de sufijos de `pricing/adapters/yfinance.py`.

`pg_trgm` se activa aquí porque la búsqueda por nombre es de subcadena y errata
(«Iberdola»), y con ETFs futuros la tabla crecerá un orden de magnitud. Es la
primera extensión que activa el proyecto aparte de las que trae la imagen.

Reversible: el downgrade tira la tabla. La extensión se queda — otra migración
podría estar usándola y desinstalarla en un downgrade parcial rompería cosas
ajenas a esta tabla.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "f2b84a6c1d9e73"
down_revision: str | None = "d4e15f9a3b7c62"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table(
        "listing_directory",
        sa.Column("isin", sa.String(12), nullable=False),
        sa.Column("mic", sa.String(4), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("short_name", sa.Text(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("cfi", sa.String(6), nullable=False),
        sa.Column("lei", sa.String(20), nullable=True),
        sa.Column("first_trade_date", sa.Date(), nullable=True),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("source", sa.String(8), nullable=False),
        sa.Column("seeded_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("isin", "mic", name="pk_listing_directory"),
    )
    op.create_index(
        "ix_listdir_name_trgm",
        "listing_directory",
        ["name"],
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_listdir_name_trgm", table_name="listing_directory")
    op.drop_table("listing_directory")
