"""Modelo ORM de transacciones."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Numeric, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TransactionFlow(enum.StrEnum):
    """Dirección y naturaleza del movimiento — fuente de verdad del dinero.

    PHASE-34 (ADR-0004). Sustituye la derivación del signo y la
    clasificación desde `category.kind` / `category.is_transfer`:

    - **Saldo**: se deriva de `flow` + `account.nature` (nunca de la
      categoría). `IN`/`TRANSFER_IN` entran, `OUT`/`TRANSFER_OUT` salen;
      `account.nature` decide el signo final (ASSET suma lo que entra,
      LIABILITY lo invierte).
    - **Cashflow del mes**: `gasto = Σ(flow=OUT)`, `ingreso = Σ(flow=IN)`.
      Los `TRANSFER_*` se excluyen por el propio movimiento, no por la
      categoría.

    La columna es NULLABLE: `NULL` = movimiento sin clasificar todavía
    (p. ej. tx heredada sin categoría). Contribuye 0 al saldo y queda
    fuera del cashflow, igual que el `else_=0` previo. El pipeline de
    import y los formularios escriben `flow` explícitamente (PHASE-34.3+);
    la categoría pasa a ser puramente descriptiva.
    """

    IN = "IN"
    OUT = "OUT"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"


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
    # PHASE-34 (ADR-0004): fuente de verdad del dinero a nivel de
    # transacción. NULLABLE durante la transición — `NULL` = sin
    # clasificar (contribuye 0 al saldo, fuera del cashflow). El saldo y
    # el cashflow se derivan de aquí + `account.nature`, no de la
    # categoría. Lo escribe el import (signo del extracto) y los forms.
    flow: Mapped[TransactionFlow | None] = mapped_column(
        Enum(TransactionFlow, name="transactionflow", native_enum=True),
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
    # AUDIT-2026-07 (H-04): TRUE marca un "cargo espejo" (ADEUDO/LIQUIDACIÓN
    # de tarjeta) que el SISTEMA absorbió al convertir una compra en deuda.
    # Se soft-borra (`deleted_at`) para que desaparezca del ledger, pero a
    # diferencia de un borrado de USUARIO no debe reimportarse: si el usuario
    # reimporta el mismo extracto, `find_existing_hashes` lo trata como
    # existente para no resucitar el −X y volver a descuadrar el saldo.
    absorbed_as_mirror: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    # PHASE-37.3 — override manual de tres estados sobre la clasificación
    # estructural/puntual del gasto (ver `analytics/recurrence.py`):
    #   NULL  → decide la heurística (recurrencia / fixed_expense / rol deuda).
    #   TRUE  → el usuario lo marcó como PUNTUAL (one-off, excluido de la base
    #           de gasto estructural y del runway).
    #   FALSE → el usuario lo marcó como ESTRUCTURAL (recurrente).
    # Ortogonal a `flow`: `flow` dice si es gasto/ingreso/transferencia;
    # `is_exceptional` sólo matiza, dentro de los gastos, si es recurrente.
    is_exceptional: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

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
        # PHASE-34.1 — los agregados de cashflow del dashboard filtran por
        # `flow` sobre filas activas (gasto = Σ flow=OUT, ingreso = Σ flow=IN,
        # transferencias excluidas). Índice parcial alineado con la migración
        # `z3p58r0on2q1p7` (declarado aquí para la paridad `alembic check`).
        Index(
            "ix_transactions_user_flow_active",
            "user_id",
            "flow",
            postgresql_where="deleted_at IS NULL",
        ),
    )
