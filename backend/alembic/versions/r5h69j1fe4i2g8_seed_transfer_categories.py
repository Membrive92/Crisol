"""PHASE-31.1 — Saneamiento de categorías de transferencia.

1. Inserta la categoría "Transferencia a favor" (INCOME, is_transfer)
   para todos los usuarios que ya tienen la versión EXPENSE
   "Transferencias" pero no la nueva. Una sola fila por usuario.

2. Recategoriza las transacciones existentes que están en
   "Transferencias" (EXPENSE) pero cuya descripción indica
   inequívocamente un movimiento entrante. Sólo toca tx no
   pareadas (`transfer_pair_id IS NULL`) para no romper pares ya
   confirmados manualmente.

Idempotente: re-ejecutar no duplica categorías ni recategoriza dos
veces (la segunda pasada no encuentra tx que cumplan la condición
porque ya están en la categoría INCOME).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "r5h69j1fe4i2g8"
down_revision: str | None = "q4g58i0ed3h1f7"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Para cada usuario que tiene "Transferencias" EXPENSE,
    #    crear "Transferencia a favor" INCOME si no existe.
    #    `gen_random_uuid()` viene del módulo pgcrypto, ya cargado en
    #    el bootstrap. Si no estuviera, usar uuid_generate_v4 (uuid-ossp).
    bind.execute(sa.text("""
        INSERT INTO categories (
            id, user_id, name, kind, is_transfer, color, icon,
            created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            tx_cat.user_id,
            'Transferencia a favor',
            'INCOME'::categorykind,
            TRUE,
            '#d97706',
            '💰',
            NOW(),
            NOW()
        FROM categories tx_cat
        WHERE tx_cat.name = 'Transferencias'
          AND tx_cat.kind = 'EXPENSE'
          AND tx_cat.is_transfer = TRUE
          AND NOT EXISTS (
              SELECT 1 FROM categories existing
              WHERE existing.user_id = tx_cat.user_id
                AND existing.name = 'Transferencia a favor'
          );
    """))

    # 2. Recategorizar transacciones cuya descripción indica
    #    inequívocamente que son entrantes pero están en la categoría
    #    EXPENSE. Sólo toca las que cumplen TODO: categoría incorrecta
    #    + descripción que matchea uno de los patrones de entrada
    #    + sin pareja ya establecida (transfer_pair_id IS NULL) para
    #    no tocar pares confirmados manualmente.
    bind.execute(sa.text("""
        UPDATE transactions t
        SET category_id = (
            SELECT id FROM categories
            WHERE user_id = t.user_id
              AND name = 'Transferencia a favor'
              AND kind = 'INCOME'
            LIMIT 1
        ),
        updated_at = NOW()
        FROM categories c_old
        WHERE t.category_id = c_old.id
          AND c_old.kind = 'EXPENSE'
          AND c_old.is_transfer = TRUE
          AND c_old.name = 'Transferencias'
          AND t.deleted_at IS NULL
          AND t.transfer_pair_id IS NULL
          AND (
              t.description ILIKE '%RECIBIDA%'
           OR t.description ILIKE '%RECIBIDO%'
           OR t.description ILIKE '%ABONO POR TRANSFER%'
           OR t.description ILIKE '%ABONO TRANSFER%'
           OR t.description ILIKE '%INGRESO POR TRANSFER%'
           OR t.description ILIKE '%TRANSFERENCIA DESDE%'
           OR t.description ILIKE '%TRASPASO RECIBIDO%'
          );
    """))


def downgrade() -> None:
    # No revertimos el recategorizado del paso 2: la información de
    # qué tx fue tocada se ha perdido y volver a EXPENSE rompería el
    # saldo del usuario otra vez. Sí permitimos eliminar la categoría
    # "Transferencia a favor" SI no tiene tx asociadas; si las tiene
    # (porque el upgrade movió tx hacia ella), bloqueamos el downgrade
    # con un mensaje claro para que el operador decida.
    bind = op.get_bind()
    blocking = bind.execute(sa.text("""
        SELECT COUNT(*) FROM transactions t
        JOIN categories c ON c.id = t.category_id
        WHERE c.name = 'Transferencia a favor'
          AND c.kind = 'INCOME'
          AND c.is_transfer = TRUE
    """)).scalar()
    if blocking and int(blocking) > 0:
        raise RuntimeError(
            f"PHASE-31.1 downgrade bloqueado: {blocking} transacciones "
            "asignadas a 'Transferencia a favor'. Recategorízalas antes "
            "de hacer downgrade."
        )
    bind.execute(sa.text("""
        DELETE FROM categories
        WHERE name = 'Transferencia a favor'
          AND kind = 'INCOME'
          AND is_transfer = TRUE;
    """))
