"""Reconciliación de transacciones `expected` con imports (PHASE-17.3).

Cuando el pipeline de imports trae una transacción que matchea una
`expected` previamente creada por el cron de autoposteo, en vez de
crear un duplicado se "fusiona" — la `expected` recibe el
`import_hash` del fichero y se considera conciliada con el banco.

Criterios de match (todos deben cumplirse):

- Mismo `user_id`.
- `source = expected` y `import_hash IS NULL` (no conciliada
  todavía).
- `deleted_at IS NULL` (no en papelera).
- Mismo `amount` (exacto — fixed_expenses tienen cantidad estable).
- Mismo `currency`.
- `occurred_at` dentro de ±DAYS_TOLERANCE días respecto a la nueva
  tx (cubre cargos que el banco mueve un par de días por
  fines de semana / festivos).
- Prefijo común normalizado entre descripciones >= MIN_COMMON_PREFIX
  (= 6 chars, mismo umbral que el detector PHASE-14.7) — evita
  match con un cargo no relacionado de mismo importe.

Si encuentra varios candidatos (raro), se elige el más cercano en
fecha. Si no encuentra ninguno, devuelve `None` y el caller crea
la tx normal con `source=import`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.fixed_expenses.detector import (
    MIN_COMMON_PREFIX,
    _common_prefix,
    normalize_merchant,
)
from app.modules.personal_finance.transactions.models import (
    Transaction,
    TransactionSource,
)

DAYS_TOLERANCE = 3


async def reconcile_with_expected(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    occurred_at: datetime,
    amount: Decimal,
    currency: str,
    description: str | None,
    import_hash: str,
) -> Transaction | None:
    """Busca una tx `expected` candidata y, si la encuentra, le asigna
    el `import_hash` y refresca su `description` con la del import (la
    del banco suele ser más legible). Devuelve la tx fusionada o
    `None` si no hubo match.

    El caller debe seguir contando esa fila como "no insertada" — la
    operación cuenta como reconciliación, no como creación.
    """
    if description is None:
        return None
    normalized = normalize_merchant(description)
    if len(normalized) < MIN_COMMON_PREFIX:
        return None

    # Normalizamos a UTC: las txs en BD son TIMESTAMPTZ, pero el caller
    # puede pasar naive (parser de CSV) o aware. Si es naive, asumimos
    # UTC — el resto del pipeline también lo asume.
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=UTC)

    window_start = occurred_at - timedelta(days=DAYS_TOLERANCE)
    window_end = occurred_at + timedelta(days=DAYS_TOLERANCE)

    query = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .where(Transaction.source == TransactionSource.EXPECTED)
        .where(Transaction.import_hash.is_(None))
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.amount == amount)
        .where(Transaction.currency == currency)
        .where(Transaction.occurred_at >= window_start)
        .where(Transaction.occurred_at <= window_end)
    )
    rows = (await db.execute(query)).scalars().all()
    if not rows:
        return None

    # Filtrar por prefijo común. Más sencillo en Python que en SQL —
    # el set candidato ya es pequeño (< 50 expected pendientes por
    # user en escenarios reales).
    candidates: list[Transaction] = []
    for tx in rows:
        if tx.description is None:
            continue
        tx_normalized = normalize_merchant(tx.description)
        if _common_prefix(normalized, tx_normalized) >= MIN_COMMON_PREFIX:
            candidates.append(tx)

    if not candidates:
        return None

    # Si hay varios, elegimos el más cercano en fecha — el banco
    # suele cargar como mucho 1-2 días de retraso, así que el más
    # cercano en fecha es el match más probable. Normalizamos
    # ambos a UTC-aware antes de restar.
    def _aware(dt: datetime) -> datetime:
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)

    best = min(
        candidates,
        key=lambda tx: abs((_aware(tx.occurred_at) - occurred_at).total_seconds()),
    )
    best.import_hash = import_hash
    # Refrescar description con la del banco (más legible que el
    # raw_description que vino del fixed_expense original).
    best.description = description
    return best
