"""Modelos ORM de WebAuthn (passkeys)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WebAuthnCredential(Base):
    """Credencial WebAuthn registrada por un usuario.

    Guarda solo la clave pública: la privada vive en la secure enclave del
    dispositivo y nunca sale de él. `sign_count` se actualiza con cada uso
    para detectar clones (si baja, algo raro pasa).
    """

    __tablename__ = "webauthn_credentials"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # `credential_id` es lo que el navegador envía durante autenticación.
    # Único globalmente (es lo que identifica una credencial entre todas).
    credential_id: Mapped[bytes] = mapped_column(
        LargeBinary, nullable=False, unique=True
    )
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sign_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Transports declarados por el authenticator (usb, nfc, ble, internal,
    # hybrid). Lo guardamos como CSV para no añadir un Array PG-only.
    transports: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Etiqueta opcional que el usuario puede dar al device ("MacBook Air").
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class WebAuthnChallenge(Base):
    """Challenge emitido para un flow de registro/autenticación.

    Se borra al verificar (o expira automáticamente). Sirve para que el
    backend no acepte la misma firma dos veces y para correlacionar
    flujos discoverable (sin email).
    """

    __tablename__ = "webauthn_challenges"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Para registro siempre hay user_id. Para autenticación con email
    # también. Para flujos discoverable (sin email) el user_id sale de
    # la credencial al verificar; pero por simplicidad de MVP exigimos
    # email en /authenticate-options, así que siempre hay user_id.
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    challenge: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    # `purpose`: "register" o "authenticate" — defensa en profundidad
    # contra mezclar challenges entre flujos.
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
