"""Modelo ORM del usuario."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

CYCLE_START_DAY_MIN = 1
CYCLE_START_DAY_MAX = 28
"""Rango admisible del día que abre el ciclo del usuario.

Se queda en 28 a propósito, no por prudencia: con `D ≤ 28` todo mes tiene ese
día y el ciclo nunca necesita clamping de fin de mes. Con 29-31 haría falta
decidir qué es «el 31 de febrero», y esa decisión es una charca de bugs a
cambio de cubrir un caso que nadie tiene.
"""


class User(Base):
    """Tabla de usuarios."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            f"cycle_start_day BETWEEN {CYCLE_START_DAY_MIN} AND {CYCLE_START_DAY_MAX}",
            name="ck_users_cycle_start_day_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    cycle_start_day: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True,
    )
    """Día (1-28) en que EMPIEZA el mes del usuario a efectos de presentación.

    `NULL` = mes natural, que es el estado correcto por defecto de todo el
    mundo y no un hueco por rellenar: por eso la columna no tiene default
    numérico. Un `1` por defecto afirmaría que el usuario declaró que su mes
    empieza el día 1 — indistinguible de un dato real y falso (PHASE-44.11).

    Es una convención de PRESENTACIÓN. Ninguna query de dinero (saldo,
    patrimonio, cuadro de deuda, ancla de extracto) puede leer esta columna;
    `tests/test_user_cycle.py::test_el_ciclo_no_mueve_ni_un_centimo` lo afirma.
    """
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
