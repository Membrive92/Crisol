"""Detector heurístico de subscripciones recurrentes (PHASE-13.1).

Sin IA por ahora — pura inspección de patrones de transacciones.
Si los resultados son malos en producción, una sub-fase futura
puede añadir un paso de Ollama para agrupar descripciones
inconsistentes.

Algoritmo:

1. Cargar las transacciones activas del usuario en la ventana de
   detección (últimos 6 meses por defecto).
2. Agrupar por `(merchant_normalized, amount, currency)`. Cada
   grupo representa "el mismo cargo".
3. Para cada grupo con >= MIN_OCCURRENCES (3 por defecto):
   a. Calcular gaps entre fechas consecutivas.
   b. Calcular media y desviación estándar de los gaps.
   c. Si la desviación relativa (std/media) < CADENCE_VARIANCE_MAX
      Y la media cae en alguna de las ventanas conocidas (semanal,
      quincenal, mensual, trimestral, anual) → es candidato.
4. Devolver `Candidate` con todos los datos derivados que el service
   necesita para crear/actualizar el row en BD.

La normalización de merchant la hace `normalize_merchant`. Mismo
tx hash que usaríamos para dedup de imports — minúsculas + sólo
alfanuméricos + primeros 30 chars.
"""

from __future__ import annotations

import re
import statistics
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.personal_finance.transactions.models import Transaction

# Mínimo de ocurrencias para considerar un patrón regular.
MIN_OCCURRENCES = 3

# Desviación estándar máxima respecto a la media (relativa) para que
# la cadencia se considere "regular". 0.30 = 30% de error tolerado.
CADENCE_VARIANCE_MAX = 0.30

# Ventanas de cadencia conocidas (mín, max días).
CADENCE_WINDOWS: list[tuple[int, int, int]] = [
    (6, 8, 7),       # semanal
    (13, 16, 14),    # quincenal
    (26, 35, 30),    # mensual
    (85, 95, 90),    # trimestral
    (175, 190, 180), # semestral
    (355, 375, 365), # anual
]

# Ventana de inspección por defecto: 6 meses hacia atrás.
DEFAULT_LOOKBACK_DAYS = 180

# Longitud máxima del merchant normalizado.
MERCHANT_MAX_LEN = 30

# PHASE-14.7: longitud mínima de prefijo común para considerar dos
# grupos como el mismo merchant. "netflixsuscrip" + "netflixcom"
# comparten "netflix" (7 chars) → match. "spotify" + "spaceshop"
# comparten "sp" → no match. 6 es un punto medio razonable.
MIN_COMMON_PREFIX = 6


def normalize_merchant(description: str | None) -> str:
    """Lowercase + sólo `[a-z0-9]` + primeros 30 chars.

    Pensada para colapsar variaciones del mismo comercio
    ("NETFLIX.COM", "Netflix Premium", "PRO_NETFLIX SUSCRIP") al
    mismo bucket sin necesidad de IA. Falsa convergencia es posible
    (dos comercios con prefijo común quedarían juntos) — el usuario
    descarta el falso positivo y el detector marca ese merchant
    como `dismissed` para no re-sugerirlo.
    """
    if not description:
        return ""
    cleaned = re.sub(r"[^a-z0-9]", "", description.lower())
    return cleaned[:MERCHANT_MAX_LEN]


@dataclass(frozen=True)
class Candidate:
    """Patrón candidato a subscripción detectado."""

    merchant: str
    raw_description: str
    amount: Decimal
    currency: str
    cadence_days: int
    next_due: date
    first_seen_at: date
    last_seen_at: date
    occurrence_count: int
    confidence: float
    category_id: uuid.UUID | None


def _bucket_cadence(mean_days: float) -> int | None:
    """Devuelve la cadencia canónica (7/14/30/90/180/365) si la media
    cae en alguna ventana conocida. `None` si no encaja con ninguna
    cadencia "subscription-like".
    """
    for lo, hi, canonical in CADENCE_WINDOWS:
        if lo <= mean_days <= hi:
            return canonical
    return None


def _detect_in_group(
    occurrences: list[tuple[date, str, uuid.UUID | None]],
    *,
    merchant: str,
    amount: Decimal,
    currency: str,
) -> Candidate | None:
    """Procesa las ocurrencias de un grupo y devuelve `Candidate`
    si forman un patrón subscription-like.

    Cada `occurrence` es `(occurred_at_date, raw_description, category_id)`
    para poder rescatar el sample legible y la categoría más
    frecuente.
    """
    if len(occurrences) < MIN_OCCURRENCES:
        return None

    # Ordenar por fecha ascendente.
    sorted_occ = sorted(occurrences, key=lambda x: x[0])
    dates = [d for d, _, _ in sorted_occ]
    gaps = [
        (dates[i] - dates[i - 1]).days for i in range(1, len(dates))
    ]
    if not gaps or any(g <= 0 for g in gaps):
        return None

    mean_gap = statistics.mean(gaps)
    canonical = _bucket_cadence(mean_gap)
    if canonical is None:
        return None

    # std=0 con un solo gap (n=1 caso de 2 occurrences, pero ya filtramos
    # por MIN_OCCURRENCES=3 → al menos 2 gaps). Para n>=2, statistics.stdev
    # funciona; para variance=0 (cadencia perfecta), confidence=1.
    if len(gaps) >= 2:
        std_gap = statistics.stdev(gaps)
        relative_variance = std_gap / mean_gap if mean_gap > 0 else 1.0
    else:
        relative_variance = 0.0

    if relative_variance > CADENCE_VARIANCE_MAX:
        return None

    confidence = max(0.0, min(1.0, 1.0 - relative_variance))

    # Categoría más común entre las occurrences (o None si todas son None).
    category_counts: dict[uuid.UUID | None, int] = defaultdict(int)
    for _, _, cat in sorted_occ:
        category_counts[cat] += 1
    dominant_category = max(category_counts, key=lambda k: category_counts[k])

    # Sample legible: la raw_description más reciente (no necesariamente
    # representativa del 100% del grupo, pero la más útil para el usuario).
    raw_sample = sorted_occ[-1][1]

    return Candidate(
        merchant=merchant,
        raw_description=raw_sample,
        amount=amount,
        currency=currency,
        cadence_days=canonical,
        next_due=dates[-1] + timedelta(days=canonical),
        first_seen_at=dates[0],
        last_seen_at=dates[-1],
        occurrence_count=len(occurrences),
        confidence=round(confidence, 3),
        category_id=dominant_category,
    )


async def detect_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    today: date | None = None,
) -> list[Candidate]:
    """Devuelve todos los patrones subscription-like del usuario.

    Sólo considera transacciones activas (excluye soft-deleted
    PHASE-10.1). El service decide qué hacer con cada `Candidate`
    (crear `pending`, refrescar existente, ignorar si está
    `dismissed`).
    """
    today = today or datetime.now().date()
    since = today - timedelta(days=lookback_days)

    query = (
        select(
            Transaction.occurred_at,
            Transaction.description,
            Transaction.amount,
            Transaction.currency,
            Transaction.category_id,
        )
        .where(Transaction.user_id == user_id)
        .where(Transaction.deleted_at.is_(None))
        .where(Transaction.occurred_at >= datetime.combine(since, datetime.min.time()))
    )
    rows = (await db.execute(query)).all()

    grouped: dict[tuple[str, Decimal, str], list[tuple[date, str, uuid.UUID | None]]] = (
        defaultdict(list)
    )
    for occurred_at, description, amount, currency, category_id in rows:
        merchant = normalize_merchant(description)
        if not merchant:
            continue
        key = (merchant, Decimal(amount), currency)
        grouped[key].append(
            (occurred_at.date(), description or "", category_id)
        )

    # PHASE-14.7: fusionar grupos con prefijo común grande +
    # mismo amount + mismo currency. Captura "NETFLIX.COM" /
    # "NETFLIX PREMIUM" / "PRO_NETFLIX" como mismo merchant sin
    # necesitar IA. La fusión preserva el merchant del grupo
    # más grande (más representativo) y concatena occurrences.
    grouped = _merge_by_common_prefix(grouped)

    candidates: list[Candidate] = []
    for (merchant, amount, currency), occurrences in grouped.items():
        candidate = _detect_in_group(
            occurrences,
            merchant=merchant,
            amount=amount,
            currency=currency,
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _common_prefix(a: str, b: str) -> int:
    """Longitud del prefijo común entre dos strings."""
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def _merge_by_common_prefix(
    grouped: dict[tuple[str, Decimal, str], list[tuple[date, str, uuid.UUID | None]]],
) -> dict[tuple[str, Decimal, str], list[tuple[date, str, uuid.UUID | None]]]:
    """Fusiona grupos cuyo merchant comparta `MIN_COMMON_PREFIX`+
    chars Y mismo amount Y mismo currency.

    Algoritmo: agrupa por (amount, currency), ordena los merchants
    de cada bucket por longitud descendente (los más largos primero
    — preferimos preservar nombres más específicos como llave). Por
    cada pareja con prefijo común suficientemente largo, fusiona el
    más corto en el más largo. Es un solo pase O(n²) por bucket;
    para volúmenes esperados (< 100 grupos por user) trivial.
    """
    by_amount: dict[
        tuple[Decimal, str], list[tuple[str, list[tuple[date, str, uuid.UUID | None]]]]
    ] = defaultdict(list)
    for (merchant, amount, currency), occurrences in grouped.items():
        by_amount[(amount, currency)].append((merchant, occurrences))

    merged: dict[
        tuple[str, Decimal, str], list[tuple[date, str, uuid.UUID | None]]
    ] = {}
    for (amount, currency), entries in by_amount.items():
        # Sort por len(merchant) desc — el más largo se queda como llave.
        entries.sort(key=lambda e: -len(e[0]))
        # `parents[i]` apunta al index "absorbedor" del grupo i.
        parents = list(range(len(entries)))
        for i in range(len(entries)):
            if parents[i] != i:
                continue
            merchant_i = entries[i][0]
            for j in range(i + 1, len(entries)):
                if parents[j] != j:
                    continue
                merchant_j = entries[j][0]
                if _common_prefix(merchant_i, merchant_j) >= MIN_COMMON_PREFIX:
                    parents[j] = i

        # Construir el resultado fusionado.
        for i, (merchant_i, occ_i) in enumerate(entries):
            if parents[i] != i:
                continue
            occ_combined = list(occ_i)
            for j in range(i + 1, len(entries)):
                if parents[j] == i:
                    occ_combined.extend(entries[j][1])
            merged[(merchant_i, amount, currency)] = occ_combined

    return merged
