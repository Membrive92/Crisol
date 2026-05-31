"""Modelo ORM de refresh tokens."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RefreshToken(Base):
    """Tabla de refresh tokens — permite revocación y rotación."""

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # AUDIT-2026-05 — identificador público (parte izquierda de
    # `<token_id>.<secret>`). Indexado: localiza la fila con UNA query y
    # luego un único argon2 verify del secreto, en vez de escanear toda la
    # tabla.
    token_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    # AUDIT-2026-05 — linaje de rotación. Se preserva al rotar; si un token
    # revocado se reutiliza (señal de robo) se revoca toda la familia.
    family_id: Mapped[uuid.UUID] = mapped_column(
        index=True,
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(
        String(512),
        unique=True,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
