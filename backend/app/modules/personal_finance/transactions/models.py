"""Modelo ORM de transacciones."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TransactionSource(enum.StrEnum):
    """Origen de la transacción.

    `expected` (PHASE-17.2) lo emite el cron de autoposteo de
    `fixed_expenses` cuando un gasto fijo confirmado con
    `auto_post=True` llega a su `next_due`. La reconciliación con
    imports (PHASE-17.3) puede asignarle `import_hash` si después
    el banco confirma el cargo — la `source` se queda `expected`,
    el `import_hash` no nulo es el indicador de "conciliada".
    """

    MANUAL = "manual"
    IMPORT = "import"
    RECEIPT = "receipt"
    EXPECTED = "expected"


class Transaction(Base):
    """Tabla de transacciones (gastos e ingresos)."""

    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # PHASE-19.1: cada transacción pertenece obligatoriamente a una
    # cuenta del usuario. CASCADE: borrar la cuenta arrastra su
    # histórico (el service de accounts impide DELETE si hay
    # transacciones — se exige archivar para conservar el histórico).
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[TransactionSource] = mapped_column(
        nullable=False, default=TransactionSource.MANUAL
    )
    receipt_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    import_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # PHASE-19.3: enlace a la otra mitad del par cuando esta tx forma
    # parte de una transferencia interna entre cuentas del usuario.
    # NULL para movimientos normales (income/expense reales).
    # FK auto-referente con SET NULL para que al borrar una mitad la
    # otra quede huérfana (luego el frontend la mostrará como "no
    # emparejada" para que el usuario decida).
    transfer_pair_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    # Soft delete (PHASE-10.1). NULL = activa, timestamp = en papelera.
    # Las queries del módulo y del dashboard filtran por defecto
    # `deleted_at IS NULL`; los endpoints `/trash`/restore/purge son los
    # únicos que ven o tocan filas con valor.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # Partial unique para dedup de imports — incluye `AND deleted_at
        # IS NULL` para que un row trasheado no bloquee re-importar la
        # misma fila desde el fichero original. Si el usuario restaura
        # la versión trasheada después, puede acabar con un duplicado:
        # decisión consciente, prima la facilidad de re-import.
        Index(
            "uq_transactions_user_import_hash",
            "user_id",
            "import_hash",
            unique=True,
            postgresql_where="import_hash IS NOT NULL AND deleted_at IS NULL",
        ),
        # Partial index sobre user_id sólo para filas activas — todas
        # las queries de listado/agregación añaden el filtro, así que
        # mantenemos el índice "delgado".
        Index(
            "ix_transactions_user_id_active",
            "user_id",
            postgresql_where="deleted_at IS NULL",
        ),
        # AUDIT-2026-05: compuesto (user_id, occurred_at) parcial. Un
        # btree ascendente sirve igual los `ORDER BY occurred_at DESC`
        # (scan hacia atrás) y los rangos `occurred_at <= X` de
        # dashboard/drill-down/debt-history sin sort adicional.
        Index(
            "ix_transactions_user_occurred_active",
            "user_id",
            "occurred_at",
            postgresql_where="deleted_at IS NULL",
        ),
        # PHASE-19.3: agregados de cashflow/budgets/dashboard excluyen
        # las txs con `transfer_pair_id IS NOT NULL`. Filtramos sobre
        # filas activas (sin papelera) y con pareja, que son las que
        # se descuentan del cómputo.
        Index(
            "ix_transactions_transfer_pair_id",
            "transfer_pair_id",
            postgresql_where="transfer_pair_id IS NOT NULL AND deleted_at IS NULL",
        ),
    )
