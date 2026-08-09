"""Modelo del directorio oficial de valores UE/UK (PHASE-44.14, ADR-0010).

Tabla **GLOBAL** (sin `user_id`): el universo FIRDS de ESMA + FCA, sembrado por
`scripts/seed_listing_directory.py` y consultado en local, sin red. Es la capa
de identidad del buscador multi-mercado; los `Security` se crean DESDE aquí al
adoptar (`listing_key` `ext:`), nunca al revés.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ListingDirectoryEntry(Base):
    """Un instrumento admitido a negociación en una plaza, según FIRDS.

    `mic` es el MIC **OPERATIVO** (XETR), no el segmento con el que reporta
    FIRDS (XETA): la normalización la hace el seed contra ISO 10383 para que
    esta columna hable el mismo vocabulario que `securities.exchange` y que el
    mapa de sufijos del proveedor de precios.
    """

    __tablename__ = "listing_directory"

    isin: Mapped[str] = mapped_column(String(12), primary_key=True)
    mic: Mapped[str] = mapped_column(String(4), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    """`FullNm` del registro FIRDS — el nombre registral, tal cual."""
    short_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    """`ShrtNm`. En ESMA suele llevar el ticker local (`ITX/AC 0.03` para
    Inditex), así que se busca también contra él — es lo que hace que teclear
    `ITX` encuentre a Inditex por DATOS, no por un alias escrito a mano."""
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    """`NtnlCcy`. Verificado en el fichero real: la FCA publica XLON en GBP
    (libras), no en GBp — los peniques son cosa del proveedor de precios."""
    cfi: Mapped[str] = mapped_column(String(6), nullable=False)
    lei: Mapped[str | None] = mapped_column(String(20), nullable=True)
    first_trade_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(String(8), nullable=False)
    """`ESMA` | `FCA` — de qué registro salió la fila."""
    seeded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index(
            "ix_listdir_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )
