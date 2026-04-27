"""Lógica de negocio del módulo imports.

Pipeline síncrono:

    1. Crear job en estado `processing`.
    2. Parsear el fichero (CSV o XLSX).
    3. Para cada fila: aplicar mapping → validar → calcular hash →
       deduplicar → crear Transaction.
    4. Marcar job como `completed` (o `failed` si el parser falla).
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai import service as ai_service
from app.modules.ai.exceptions import AiError
from app.modules.imports.models import ImportJob, ImportJobStatus
from app.modules.imports.parser import (
    NoTablesInPdfError,
    ParseError,
    parse_file,
    render_pdf_pages_to_png,
)
from app.modules.imports.repository import create_job, find_existing_hashes
from app.modules.imports.schemas import ImportColumnMappings
from app.modules.personal_finance.categories.models import Category
from app.modules.transactions.models import Transaction, TransactionSource

MAX_ERROR_LOG = 100
DEFAULT_CURRENCY = "EUR"
MAX_VISION_PDF_PAGES = 5

# Mapping forzado para el flujo de visión: el modelo siempre devuelve estas
# claves y no usamos las del usuario en este caso.
VISION_FORCED_MAPPING = ImportColumnMappings(
    amount="amount",
    occurred_at="occurred_at",
    description="description",
    category_name=None,
)

DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
)


@dataclass(slots=True)
class ParsedRow:
    """Fila ya validada lista para persistir."""

    amount: Decimal
    occurred_at: datetime
    description: str | None
    category_id: uuid.UUID | None
    import_hash: str


async def run_import(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    filename: str,
    content_type: str | None,
    payload: bytes,
    mappings: ImportColumnMappings,
    currency: str = DEFAULT_CURRENCY,
    default_category_id: uuid.UUID | None = None,
) -> ImportJob:
    """Ejecuta el pipeline completo y devuelve el job ya finalizado."""
    job = ImportJob(
        user_id=user_id,
        filename=filename[:255],
        status=ImportJobStatus.PROCESSING,
        column_mappings=mappings.model_dump(),
        error_log=[],
    )
    job = await create_job(db, job)

    effective_mappings = mappings
    try:
        rows = parse_file(payload, filename, content_type)
    except NoTablesInPdfError:
        # PDF sin texto extraíble — caemos al pipeline de visión local.
        try:
            rows = await _parse_pdf_with_vision(payload)
        except (ParseError, AiError) as e:
            job.status = ImportJobStatus.FAILED
            job.error_log = [{"row": 0, "error": f"Visión PDF falló: {e}"}]
            await db.flush()
            await db.refresh(job)
            return job
        # Las filas vienen con keys fijas: ignoramos el mapping del usuario.
        effective_mappings = VISION_FORCED_MAPPING
    except ParseError as e:
        job.status = ImportJobStatus.FAILED
        job.error_log = [{"row": 0, "error": str(e)}]
        await db.flush()
        await db.refresh(job)
        return job

    job.rows_total = len(rows)

    if default_category_id is not None:
        valid = await _user_owns_category(db, user_id, default_category_id)
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="default_category_id no pertenece al usuario",
            )

    category_lookup = await _build_category_lookup(db, user_id)

    parsed: list[ParsedRow] = []
    errors: list[dict[str, object]] = []

    for idx, raw in enumerate(rows, start=1):
        try:
            parsed_row = _parse_row(
                raw,
                mappings=effective_mappings,
                user_id=user_id,
                currency=currency.upper(),
                category_lookup=category_lookup,
                default_category_id=default_category_id,
            )
        except _RowError as e:
            if len(errors) < MAX_ERROR_LOG:
                errors.append({"row": idx, "error": str(e)})
            continue
        parsed.append(parsed_row)

    seen_hashes_in_batch: set[str] = set()
    deduped: list[ParsedRow] = []
    for p in parsed:
        if p.import_hash in seen_hashes_in_batch:
            continue
        seen_hashes_in_batch.add(p.import_hash)
        deduped.append(p)

    existing = await find_existing_hashes(db, user_id, [p.import_hash for p in deduped])
    skipped_in_batch = len(parsed) - len(deduped)

    inserted = 0
    for p in deduped:
        if p.import_hash in existing:
            continue
        db.add(
            Transaction(
                user_id=user_id,
                category_id=p.category_id,
                amount=p.amount,
                currency=currency.upper(),
                occurred_at=p.occurred_at,
                description=p.description,
                source=TransactionSource.IMPORT,
                import_hash=p.import_hash,
            )
        )
        inserted += 1

    skipped_existing = len(deduped) - inserted

    job.rows_ok = inserted
    job.rows_failed = len(errors)
    job.rows_skipped = skipped_in_batch + skipped_existing
    job.error_log = errors
    job.status = ImportJobStatus.COMPLETED
    await db.flush()
    await db.refresh(job)
    return job


# ─────────────────────────────────────────────────────────────────────────────
# Internals
# ─────────────────────────────────────────────────────────────────────────────


async def _parse_pdf_with_vision(payload: bytes) -> list[dict[str, str]]:
    """Renderiza el PDF a imágenes y las pasa al modelo de visión.

    Devuelve filas con las keys fijas `amount`, `occurred_at`, `description`
    para que el resto del pipeline las trate igual que las parseadas con
    `parse_file`.

    Limita a `MAX_VISION_PDF_PAGES` páginas: la inferencia es cara y los
    extractos típicos rara vez tienen más de 3-4 páginas relevantes.
    """
    images = render_pdf_pages_to_png(payload, max_pages=MAX_VISION_PDF_PAGES)
    if not images:
        raise ParseError("PDF sin páginas renderizables")

    rows: list[dict[str, str]] = []
    for image in images:
        page_rows = await ai_service.extract_bank_statement_page(image)
        for r in page_rows:
            rows.append(
                {
                    "amount": str(r.amount),
                    "occurred_at": r.occurred_at,
                    "description": r.description,
                }
            )
    return rows


class _RowError(ValueError):
    """Error de validación de una fila concreta."""


def _parse_row(
    raw: dict[str, str],
    *,
    mappings: ImportColumnMappings,
    user_id: uuid.UUID,
    currency: str,
    category_lookup: dict[str, uuid.UUID],
    default_category_id: uuid.UUID | None,
) -> ParsedRow:
    """Aplica mapping + validación + hash a una fila."""
    amount_raw = raw.get(mappings.amount, "").strip()
    occurred_raw = raw.get(mappings.occurred_at, "").strip()
    description_raw = (
        raw.get(mappings.description, "").strip() if mappings.description else ""
    )
    category_name_raw = (
        raw.get(mappings.category_name, "").strip() if mappings.category_name else ""
    )

    if not amount_raw:
        raise _RowError(f"columna '{mappings.amount}' vacía")
    if not occurred_raw:
        raise _RowError(f"columna '{mappings.occurred_at}' vacía")

    amount = _parse_amount(amount_raw)
    occurred_at = _parse_datetime(occurred_raw)
    description = description_raw or None

    category_id: uuid.UUID | None = default_category_id
    if category_name_raw:
        match = category_lookup.get(category_name_raw.casefold())
        if match is not None:
            category_id = match
        # si no matchea, se queda con el default (o None) — silencioso

    import_hash = _compute_hash(
        user_id=user_id,
        amount=amount,
        currency=currency,
        occurred_at=occurred_at,
        description=description,
    )

    return ParsedRow(
        amount=amount,
        occurred_at=occurred_at,
        description=description,
        category_id=category_id,
        import_hash=import_hash,
    )


def _parse_amount(value: str) -> Decimal:
    """Acepta `1.234,56` y `1,234.56` y `25.50`."""
    cleaned = re.sub(r"\s", "", value)
    has_comma = "," in cleaned
    has_dot = "." in cleaned
    if has_comma and has_dot:
        # Asume el último es decimal
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif has_comma:
        cleaned = cleaned.replace(",", ".")
    try:
        amount = Decimal(cleaned)
    except InvalidOperation as e:
        raise _RowError(f"importe inválido: {value!r}") from e
    if amount <= 0:
        raise _RowError(f"importe debe ser positivo: {value!r}")
    return amount.quantize(Decimal("0.01"))


def _parse_datetime(value: str) -> datetime:
    """Soporta ISO y formatos europeos comunes."""
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1]
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        pass
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    raise _RowError(f"fecha inválida: {value!r}")


def _compute_hash(
    *,
    user_id: uuid.UUID,
    amount: Decimal,
    currency: str,
    occurred_at: datetime,
    description: str | None,
) -> str:
    """SHA-256 sobre los campos clave de una transacción."""
    parts = [
        str(user_id),
        f"{amount:.2f}",
        currency,
        occurred_at.isoformat(),
        (description or "").strip().casefold(),
    ]
    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


async def _build_category_lookup(
    db: AsyncSession, user_id: uuid.UUID
) -> dict[str, uuid.UUID]:
    """Mapa case-insensitive `name → id` de las categorías del usuario."""
    result = await db.execute(
        select(Category.id, Category.name).where(Category.user_id == user_id)
    )
    return {name.casefold(): cat_id for cat_id, name in result.all()}


async def _user_owns_category(
    db: AsyncSession, user_id: uuid.UUID, category_id: uuid.UUID
) -> bool:
    result = await db.execute(
        select(Category.id).where(Category.id == category_id, Category.user_id == user_id)
    )
    return result.scalar_one_or_none() is not None
