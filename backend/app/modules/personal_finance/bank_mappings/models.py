"""Modelo ORM de equivalencias banco → categoría del usuario.

PHASE-19: cuando el banco devuelve un concepto en el extracto
(p. ej. `PAGO TARJETA - RESTAURANTES`, `BIZUM RECIBIDO`,
`ABONO DE NOMINA`), guardamos una equivalencia con la categoría
del usuario para auto-asignar en próximas importaciones.

El matching es exacto (case-insensitive). El `bank_concept` se
guarda normalizado (`casefold`) para que el lookup sea trivial y
consistente con el matching del flujo de importación.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BankCategoryMapping(Base):
    """Equivalencia entre un concepto del banco y una categoría del usuario."""

    __tablename__ = "bank_category_mappings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # `bank_concept` normalizado (casefold) — el cliente nunca debería
    # mandar mayúsculas distintas para el mismo concepto.
    bank_concept: Mapped[str] = mapped_column(String(255), nullable=False)
    # Si el usuario borra la categoría que estaba mapeada, la
    # equivalencia pierde sentido — la borramos también (CASCADE).
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        # Un usuario solo puede tener una equivalencia por concepto.
        # Si re-mapea, hacemos UPSERT (cambia category_id).
        UniqueConstraint(
            "user_id", "bank_concept", name="uq_bank_mappings_user_concept"
        ),
    )
