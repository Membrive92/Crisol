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
from app.modules.personal_finance.accounts.service import ensure_account_exists
from app.modules.personal_finance.bank_mappings.repository import (
    get_mappings_for_concepts,
    normalize_concept,
    upsert_mapping as upsert_bank_mapping,
)
from app.modules.personal_finance.categories.models import Category
from app.modules.personal_finance.category_rules.models import CategoryRule
from app.modules.personal_finance.category_rules.repository import (
    find_first_matching_rule,
    list_rules_for_user,
)
from app.modules.personal_finance.fixed_expenses.reconciliation import (
    reconcile_with_expected,
)
from app.modules.personal_finance.imports.models import ImportJob, ImportJobStatus
from app.modules.personal_finance.imports.parser import (
    NoTablesInPdfError,
    ParseError,
    SmartParseAmbiguous,
    detect_format,
    parse_file,
    parse_pdf_smart,
    render_pdf_pages_to_png,
)
from app.modules.personal_finance.imports.repository import (
    create_job,
    find_existing_hashes,
    get_job_by_id,
)
from app.modules.personal_finance.imports.schemas import (
    ImportColumnMappings,
    ImportSource,
)
from app.modules.personal_finance.transactions.models import Transaction, TransactionSource

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

# Mapping forzado para el smart parser PDF: detecta la tabla de transacciones
# y devuelve filas con keys fijas (incluyendo `category_name`).
SMART_FORCED_MAPPING = ImportColumnMappings(
    amount="amount",
    occurred_at="occurred_at",
    description="description",
    category_name="category_name",
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
    account_id: uuid.UUID,
    filename: str,
    content_type: str | None,
    payload: bytes,
    mappings: ImportColumnMappings,
    currency: str = DEFAULT_CURRENCY,
    default_category_id: uuid.UUID | None = None,
) -> ImportJob:
    """Ejecuta el pipeline completo (parse + persistir) y devuelve el job.

    PHASE-19.1: `account_id` es obligatorio — todas las transacciones
    importadas se imputan a esa cuenta. Validado contra ownership
    antes de tocar nada.
    """
    await ensure_account_exists(db, account_id, user_id)
    job = ImportJob(
        user_id=user_id,
        account_id=account_id,
        filename=filename[:255],
        status=ImportJobStatus.PROCESSING,
        column_mappings=mappings.model_dump(),
        error_log=[],
    )
    job = await create_job(db, job)

    try:
        rows, effective_mappings, _ = await _parse_with_fallbacks(
            payload=payload,
            filename=filename,
            content_type=content_type,
            mappings=mappings,
        )
    except AiError as e:
        return await _mark_job_failed(db, job, f"Visión PDF falló: {e}")
    except ParseError as e:
        return await _mark_job_failed(db, job, str(e))

    if default_category_id is not None:
        valid = await _user_owns_category(db, user_id, default_category_id)
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="default_category_id no pertenece al usuario",
            )

    await _process_and_persist(
        db,
        user_id,
        job=job,
        account_id=account_id,
        rows=rows,
        effective_mappings=effective_mappings,
        currency=currency,
        default_category_id=default_category_id,
    )
    return job


async def run_preview(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    account_id: uuid.UUID,
    filename: str,
    content_type: str | None,
    payload: bytes,
    mappings: ImportColumnMappings,
    currency: str = DEFAULT_CURRENCY,
    default_category_id: uuid.UUID | None = None,
    force_vision: bool = False,
) -> ImportJob:
    """Parsea el fichero y guarda las filas detectadas en el job en
    estado PREVIEW, sin persistir transacciones.

    El frontend usa el job devuelto para mostrar las filas al usuario;
    cuando confirma, llama `run_commit(job_id)` que las persiste.

    `force_vision=True` salta pdfplumber y va directo al fallback
    de IA con visión (PHASE-4: opt-in para PDFs raros).
    """
    await ensure_account_exists(db, account_id, user_id)
    if default_category_id is not None:
        valid = await _user_owns_category(db, user_id, default_category_id)
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="default_category_id no pertenece al usuario",
            )

    job = ImportJob(
        user_id=user_id,
        account_id=account_id,
        filename=filename[:255],
        status=ImportJobStatus.PREVIEW,
        column_mappings=mappings.model_dump(),
        error_log=[],
    )
    job = await create_job(db, job)

    try:
        rows, effective_mappings, source = await _parse_with_fallbacks(
            payload=payload,
            filename=filename,
            content_type=content_type,
            mappings=mappings,
            force_vision=force_vision,
        )
    except AiError as e:
        return await _mark_job_failed(db, job, f"Visión PDF falló: {e}")
    except ParseError as e:
        return await _mark_job_failed(db, job, str(e))

    job.rows_total = len(rows)
    job.preview_payload = {
        "rows": rows,
        "effective_mappings": effective_mappings.model_dump(),
        "currency": currency.upper(),
        "default_category_id": (
            str(default_category_id) if default_category_id else None
        ),
        "source": source.value,
        "account_id": str(account_id),
    }
    await db.flush()
    await db.refresh(job)
    return job


async def run_commit(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    job_id: uuid.UUID,
    category_overrides: dict[str, uuid.UUID] | None = None,
) -> ImportJob:
    """Confirma un job en estado PREVIEW: persiste sus filas como
    transacciones y deja el job en COMPLETED.

    `category_overrides` es un mapping `concepto_banco → category_id`
    proporcionado por el usuario en el preview. Para cada fila cuyo
    `category_name` (concepto del banco, normalizado) matchee una
    entry, la transacción se persiste con esa categoría. Además, las
    equivalencias se guardan en `bank_category_mappings` para que
    futuras importaciones las apliquen automáticamente (autoaprendizaje
    PHASE-19). Cualquier `category_id` del override debe pertenecer al
    usuario — si no, se ignora silenciosamente.

    Idempotente sólo en el sentido de que un job ya en COMPLETED
    devuelve un 409 al caller — no re-procesa.
    """
    job = await get_job_by_id(db, job_id, user_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job no encontrado"
        )
    if job.status != ImportJobStatus.PREVIEW:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job en estado {job.status.value}, no se puede confirmar",
        )
    if not job.preview_payload:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job sin filas en preview",
        )

    payload_data = job.preview_payload
    rows_raw = payload_data.get("rows") or []
    effective_mappings = ImportColumnMappings.model_validate(
        payload_data["effective_mappings"]
    )
    currency = payload_data.get("currency") or DEFAULT_CURRENCY
    default_category_id_raw = payload_data.get("default_category_id")
    default_category_id = (
        uuid.UUID(default_category_id_raw) if default_category_id_raw else None
    )
    account_id_raw = payload_data.get("account_id") or (
        str(job.account_id) if job.account_id else None
    )
    if not account_id_raw:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El job no tiene cuenta asignada — no se puede confirmar.",
        )
    account_id = uuid.UUID(account_id_raw)
    await ensure_account_exists(db, account_id, user_id)

    # Validar y persistir overrides como equivalencias antes de procesar
    # las filas, para que el lookup encuentre las categorías correctas.
    valid_overrides: dict[str, uuid.UUID] = {}
    if category_overrides:
        valid_overrides = await _persist_user_category_overrides(
            db, user_id, category_overrides
        )

    job.status = ImportJobStatus.PROCESSING
    job.error_log = []
    job.rows_ok = 0
    job.rows_failed = 0
    job.rows_skipped = 0
    await db.flush()

    await _process_and_persist(
        db,
        user_id,
        job=job,
        account_id=account_id,
        rows=rows_raw,
        effective_mappings=effective_mappings,
        currency=currency,
        default_category_id=default_category_id,
        category_overrides=valid_overrides,
    )
    # No borramos preview_payload — útil para auditoría / debugging.
    return job


async def _persist_user_category_overrides(
    db: AsyncSession,
    user_id: uuid.UUID,
    overrides: dict[str, uuid.UUID],
) -> dict[str, uuid.UUID]:
    """Valida que cada `category_id` pertenece al usuario y guarda la
    equivalencia (UPSERT). Devuelve los pares válidos con el concepto
    ya normalizado para que el caller los use al procesar filas.

    Conceptos con `category_id` ajeno se filtran silenciosamente —
    es un error del cliente, no del usuario, y no debe abortar la
    importación entera.
    """
    # Carga las categorías del usuario una vez para validar todas.
    user_cat_ids = {
        cat_id
        for (cat_id,) in (
            await db.execute(
                select(Category.id).where(Category.user_id == user_id)
            )
        ).all()
    }

    valid: dict[str, uuid.UUID] = {}
    for raw_concept, cat_id in overrides.items():
        if cat_id not in user_cat_ids:
            continue
        normalized = normalize_concept(raw_concept)
        if not normalized:
            continue
        await upsert_bank_mapping(
            db, user_id, bank_concept=normalized, category_id=cat_id
        )
        valid[normalized] = cat_id
    return valid


# ─────────────────────────────────────────────────────────────────────────────
# Internals: procesamiento de filas (parse + dedup + reconcile + persistir)
# ─────────────────────────────────────────────────────────────────────────────


async def _process_and_persist(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    job: ImportJob,
    account_id: uuid.UUID,
    rows: list[dict[str, str]],
    effective_mappings: ImportColumnMappings,
    currency: str,
    default_category_id: uuid.UUID | None,
    category_overrides: dict[str, uuid.UUID] | None = None,
) -> None:
    """Toma filas crudas y las convierte en transacciones persistidas.

    Compartido por `run_import` (flujo directo) y `run_commit` (flujo
    en dos pasos con preview). Modifica el `job` in-place: actualiza
    counts, error_log y status.

    Si la fila tiene `category_name` y matchea una equivalencia previa
    en `bank_category_mappings`, se aplica esa categoría (override
    explícito del usuario gana sobre la equivalencia previa, que gana
    sobre el lookup por nombre exacto en `categories`).
    """
    job.rows_total = len(rows)
    category_lookup = await _build_category_lookup(db, user_id)

    # Carga equivalencias `bank_concept → category_id` para los
    # conceptos presentes en las filas. Combina con los overrides del
    # usuario; los overrides ganan en caso de colisión.
    bank_concepts_in_rows = [
        raw.get(effective_mappings.category_name or "", "")
        for raw in rows
        if effective_mappings.category_name
    ]
    saved_mappings = (
        await get_mappings_for_concepts(db, user_id, bank_concepts_in_rows)
        if bank_concepts_in_rows
        else {}
    )
    if category_overrides:
        saved_mappings = {**saved_mappings, **category_overrides}

    # PHASE-20: reglas de categorización del usuario (rules engine).
    # Ya vienen ordenadas por priority asc (el repository las ordena).
    rules = await list_rules_for_user(db, user_id, enabled_only=True)

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
                bank_mappings=saved_mappings,
                rules=rules,
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
    reconciled = 0
    for p in deduped:
        if p.import_hash in existing:
            continue
        # PHASE-17.3: si una tx `expected` casa con esta fila, en
        # lugar de crear duplicada le asignamos el `import_hash` y
        # actualizamos su descripción. Cuenta como reconciliación,
        # no como inserción.
        match = await reconcile_with_expected(
            db,
            user_id,
            account_id=account_id,
            occurred_at=p.occurred_at,
            amount=p.amount,
            currency=currency.upper(),
            description=p.description,
            import_hash=p.import_hash,
        )
        if match is not None:
            reconciled += 1
            continue
        db.add(
            Transaction(
                user_id=user_id,
                account_id=account_id,
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

    skipped_existing = len(deduped) - inserted - reconciled

    job.rows_ok = inserted + reconciled
    job.rows_failed = len(errors)
    job.rows_skipped = skipped_in_batch + skipped_existing
    job.error_log = errors
    job.status = ImportJobStatus.COMPLETED
    await db.flush()
    await db.refresh(job)


async def _mark_job_failed(
    db: AsyncSession, job: ImportJob, error: str
) -> ImportJob:
    job.status = ImportJobStatus.FAILED
    job.error_log = [{"row": 0, "error": error}]
    await db.flush()
    await db.refresh(job)
    return job


# ─────────────────────────────────────────────────────────────────────────────
# Internals
# ─────────────────────────────────────────────────────────────────────────────


async def _parse_with_fallbacks(
    *,
    payload: bytes,
    filename: str,
    content_type: str | None,
    mappings: ImportColumnMappings,
    force_vision: bool = False,
) -> tuple[list[dict[str, str]], ImportColumnMappings, ImportSource]:
    """Pipeline de parseo con cascada de fallbacks.

    PDF: intenta `parse_pdf_smart` (detecta tabla de transacciones,
    keys fijas). Si la heurística no es confiable, cae al `parse_file`
    legacy con el mapping del usuario. Si pdfplumber no encuentra
    tablas, fallback a visión local. Cualquier `ParseError` final se
    propaga al caller.

    `force_vision=True` salta pdfplumber y va directo al fallback
    de visión (PHASE-4 opt-in: el usuario lo pide desde la UI).

    CSV/XLSX: directo al `parse_file` con el mapping del usuario.
    """
    fmt = detect_format(filename, content_type)
    if fmt == "csv":
        rows = parse_file(payload, filename, content_type)
        return rows, mappings, ImportSource.CSV
    if fmt == "xlsx":
        rows = parse_file(payload, filename, content_type)
        return rows, mappings, ImportSource.XLSX

    # PDF
    if force_vision:
        rows = await _parse_pdf_with_vision(payload)
        return rows, VISION_FORCED_MAPPING, ImportSource.VISION

    try:
        rows = parse_pdf_smart(payload)
        return rows, SMART_FORCED_MAPPING, ImportSource.PDFPLUMBER_SMART
    except NoTablesInPdfError:
        rows = await _parse_pdf_with_vision(payload)
        return rows, VISION_FORCED_MAPPING, ImportSource.VISION
    except SmartParseAmbiguous:
        # Heurística no encontró una tabla clara: caemos al legacy
        # parser que concatena todas las tablas y deja al usuario
        # mapear las columnas a mano (comportamiento histórico).
        rows = parse_file(payload, filename, content_type)
        return rows, mappings, ImportSource.PDFPLUMBER_LEGACY


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
    bank_mappings: dict[str, uuid.UUID] | None = None,
    rules: list[CategoryRule] | None = None,
) -> ParsedRow:
    """Aplica mapping + validación + hash a una fila.

    Prioridad para `category_id` (de mayor a menor):
    1. `bank_mappings[concepto_normalizado]` — equivalencia explícita
       del usuario (override actual o aprendida de imports previos).
    2. Match exacto en `category_lookup` por nombre case-insensitive.
    3. `rules` (PHASE-20) — primera regla habilitada que matchea por
       prioridad. Evalúa contra `concept` (category_name del banco) y
       `description` según el `field` de cada regla.
    4. `default_category_id` del usuario al subir el fichero.
    5. `None` (transacción sin categoría).
    """
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
    matched = False
    if category_name_raw:
        normalized = category_name_raw.casefold().strip()
        if bank_mappings is not None and normalized in bank_mappings:
            category_id = bank_mappings[normalized]
            matched = True
        elif (cat_match := category_lookup.get(normalized)) is not None:
            category_id = cat_match
            matched = True
    if not matched and rules:
        rule = find_first_matching_rule(
            rules, concept=category_name_raw or None, description=description
        )
        if rule is not None:
            category_id = rule.category_id

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
    """Acepta `1.234,56`, `1,234.56`, `25.50`, signos `+`/`-` y
    símbolos de moneda comunes (`€`, `$`, `£`, ` EUR`, ` USD`...).

    El sistema almacena importes siempre positivos y deduce el signo
    de la categoría (income/expense). Los extractos bancarios reales
    suelen traer gastos con signo negativo, así que aceptamos el
    signo y devolvemos el valor absoluto. La asignación correcta de
    categoría por nombre (PHASE-17.x) y la pantalla de preview es
    la responsable de coherencia gasto/ingreso. Importes a 0 o
    sin dígitos siguen rechazándose.

    Limpieza: filtra cualquier carácter que no sea dígito, separador
    decimal/miles (`.`, `,`) o signo (`+`, `-`). Eso elimina espacios,
    símbolos de moneda (€/$/£), códigos ISO al final ("3310,00 EUR")
    y cualquier otro adorno que el banco añada al PDF.
    """
    cleaned = re.sub(r"[^\d.,+-]", "", value)
    if cleaned.startswith(("+", "-")):
        cleaned = cleaned[1:]
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
    amount = abs(amount)
    if amount <= 0:
        raise _RowError(f"importe debe ser distinto de cero: {value!r}")
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
