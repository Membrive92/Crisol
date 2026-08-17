"""Lógica de negocio del módulo imports.

Pipeline síncrono:

    1. Crear job en estado `processing`.
    2. Parsear el fichero (CSV o XLSX).
    3. Para cada fila: aplicar mapping → validar → calcular hash →
       deduplicar → crear Transaction.
    4. Marcar job como `completed` (o `failed` si el parser falla).
"""

from __future__ import annotations

import asyncio
import hashlib
import itertools
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import NamedTuple

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.ai import service as ai_service
from app.modules.ai.exceptions import AiError
from app.modules.personal_finance.accounts.repository import get_account_by_id
from app.modules.personal_finance.accounts.service import (
    anchor_account_balance_at,
    ensure_account_exists,
    re_anchor_from_stored,
)
from app.modules.personal_finance.bank_mappings.repository import (
    get_mappings_for_concepts,
    normalize_concept,
)
from app.modules.personal_finance.bank_mappings.repository import (
    upsert_mapping as upsert_bank_mapping,
)
from app.modules.personal_finance.categories.models import Category, CategoryKind
from app.modules.personal_finance.category_rules.models import CategoryRule
from app.modules.personal_finance.category_rules.repository import (
    find_first_matching_rule,
    list_rules_for_user,
)
from app.modules.personal_finance.debt.reconciliation import (
    SETTLEMENT_DUPLICATE_WINDOW_DAYS,
    is_card_settlement,
)
from app.modules.personal_finance.fixed_expenses.reconciliation import (
    has_pending_expected,
    reconcile_with_expected,
)
from app.modules.personal_finance.imports.fingerprint import header_fingerprint
from app.modules.personal_finance.imports.models import ImportJob, ImportJobStatus
from app.modules.personal_finance.imports.parser import (
    NoTablesInPdfError,
    ParseError,
    SmartParseAmbiguousError,
    count_pdf_pages,
    detect_format,
    parse_file,
    parse_pdf_smart,
    parse_xlsx_smart,
    render_pdf_pages_to_png,
)
from app.modules.personal_finance.imports.repository import (
    account_fingerprints,
    accounts_holding_hashes,
    create_job,
    find_existing_hashes,
    find_live_card_settlements,
    fingerprint_accounts,
    get_job_by_id,
)
from app.modules.personal_finance.imports.schemas import (
    ImportColumnMappings,
    ImportSource,
    ImportWarning,
    ImportWarningKey,
)
from app.modules.personal_finance.transactions.models import (
    Transaction,
    TransactionFlow,
    TransactionSource,
)
from app.modules.personal_finance.transfers.service import (
    classify_import_flow,
    infer_transfer_kind,
)

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
# y devuelve filas con keys fijas (incluyendo `category_name` y, desde
# PHASE-39, `statement_balance` si el extracto trae columna Saldo).
SMART_FORCED_MAPPING = ImportColumnMappings(
    amount="amount",
    occurred_at="occurred_at",
    description="description",
    category_name="category_name",
    statement_balance="statement_balance",
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
    # PHASE-34: dirección + transfer-ness derivadas del signo del extracto
    # y la descripción. `None` = no se pudo determinar (extracto sin signo)
    # → la fila se marca para revisión.
    flow: TransactionFlow | None = None
    # PHASE-39: saldo de la cuenta según el extracto TRAS este movimiento
    # (columna Saldo). Informativo — `None` si el fichero no la trae o el
    # valor no parsea; NUNCA participa en el `import_hash` (idempotencia).
    statement_balance: Decimal | None = None
    # PHASE-46: las entradas con que se clasificó la fila, para que la segunda
    # pasada (`resolve_flows_from_balance_chain`) pueda volver a llamar al
    # MISMO clasificador con la dirección ya deducida, en vez de decidir por su
    # cuenta qué es una transferencia y arriesgarse a discrepar.
    classify_text: str | None = None
    category_is_transfer: bool = False


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
        rows, effective_mappings, _, source_header = await _parse_with_fallbacks(
            payload=payload,
            filename=filename,
            content_type=content_type,
            mappings=mappings,
        )
    except AiError as e:
        return await _mark_job_failed(db, job, f"Visión PDF falló: {e}")
    except ParseError as e:
        return await _mark_job_failed(db, job, str(e))

    # PHASE-47.A — el import DIRECTO no pasa por el preview, así que no puede
    # emitir avisos ni pedir que se reconozcan: es un camino sin pantalla. Pero
    # sí registra su formato, porque si no la cuenta nunca acumularía el suyo y
    # el guardarraíl del camino con preview avisaría de más en cada importación.
    job.header_fingerprint = header_fingerprint(source_header) if source_header else None

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
        rows, effective_mappings, source, source_header = await _parse_with_fallbacks(
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
    # PHASE-47.A — la huella sale de la cabecera REAL del fichero, que el parser
    # devuelve aparte. NO de `rows[0].keys()`: los dos smart-parsers emiten
    # claves fijas por contrato, así que ese camino daba la MISMA constante para
    # todo PDF y todo XLSX de cualquier banco — la señal no discriminaba nada y
    # el caso de julio de 2026 (dos PDF del mismo banco, productos distintos)
    # habría pasado en silencio. `None` cuando no hay cabecera que comparar
    # (visión): ausente no es lo mismo que vacía, y una huella de cadena vacía
    # casaría consigo misma en todos los ficheros a la vez.
    job.header_fingerprint = header_fingerprint(source_header) if source_header else None
    warnings = await _detect_wrong_account_warnings(
        db,
        user_id,
        account_id=account_id,
        rows=rows,
        effective_mappings=effective_mappings,
        currency=currency,
        fingerprint=job.header_fingerprint,
    )
    job.preview_payload = {
        "rows": rows,
        "effective_mappings": effective_mappings.model_dump(),
        "currency": currency.upper(),
        "default_category_id": (str(default_category_id) if default_category_id else None),
        "source": source.value,
        "account_id": str(account_id),
        "warnings": [w.model_dump(mode="json") for w in warnings],
    }
    await db.flush()
    await db.refresh(job)
    return job


def _preview_row_hashes(
    rows: list[dict[str, str]],
    mappings: ImportColumnMappings,
    *,
    user_id: uuid.UUID,
    currency: str,
) -> list[str]:
    """Hashes de dedup de las filas del preview, sin procesarlas enteras.

    Reproduce `_compute_hash` con lo mínimo —importe, divisa, fecha,
    descripción—; no pasa por `_parse_row`, que además resuelve categorías,
    aplica reglas y clasifica el `flow`, y que en un preview de sólo aviso
    sería mucho trabajo para nada.

    Deliberadamente NO reproduce el ordinal de ocurrencia: dos filas idénticas
    del mismo lote comparten aquí el hash base, así que el solape se **subestima**
    en ese caso. Preferimos avisar de menos que de más — un aviso que salta sin
    motivo se aprende a ignorar, y con él el que sí importa.
    """
    hashes: list[str] = []
    for row in rows:
        raw_amount = (row.get(mappings.amount) or "").strip()
        raw_date = (row.get(mappings.occurred_at) or "").strip()
        if not raw_amount or not raw_date:
            continue
        try:
            amount, _sign = _parse_amount_signed(raw_amount)
            occurred_at = _parse_datetime(raw_date)
        except (_RowError, ValueError):
            continue
        description = (row.get(mappings.description) if mappings.description else None) or None
        hashes.append(
            _compute_hash(
                user_id=user_id,
                amount=amount,
                currency=currency.upper(),
                occurred_at=occurred_at,
                description=description,
            )
        )
    return hashes


async def _detect_wrong_account_warnings(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    account_id: uuid.UUID,
    rows: list[dict[str, str]],
    effective_mappings: ImportColumnMappings,
    currency: str,
    fingerprint: str | None,
) -> list[ImportWarning]:
    """PHASE-47.A — ¿Este fichero parece de otra cuenta?

    Dos señales que cubren casos DISTINTOS, y conviene saber cuál sirve para
    qué: la huella de cabecera caza un fichero con el formato de otra cuenta
    —incluida la primera vez que se importa, que es el caso de julio de 2026—;
    el solape de dedup caza una RE-importación de algo que ya está en otra
    cuenta, y en julio no habría dicho nada porque era la primera vez.

    Ninguna prohíbe: el usuario puede tener razón. Devuelven avisos que el
    commit exige reconocer.
    """
    warnings: list[ImportWarning] = []
    account_names: dict[uuid.UUID, str] = {}

    async def _name(target: uuid.UUID) -> str:
        if target not in account_names:
            account = await get_account_by_id(db, target, user_id)
            account_names[target] = account.name if account else "otra cuenta"
        return account_names[target]

    if fingerprint:
        others = [
            a for a in await fingerprint_accounts(db, user_id, fingerprint) if a != account_id
        ]
        # Sólo avisa si el formato NO se ha usado nunca en la cuenta elegida:
        # un extracto que ya entró aquí antes es el caso normal, y avisar
        # entonces convertiría el guardarraíl en ruido mensual.
        own = fingerprint in {f for f in await account_fingerprints(db, user_id, account_id) if f}
        if others and not own:
            other_id = others[0]
            name = await _name(other_id)
            warnings.append(
                ImportWarning(
                    key=ImportWarningKey.HEADER_MATCHES_OTHER_ACCOUNT,
                    message=(
                        f"Este fichero tiene el mismo formato que los que importas "
                        f"en «{name}», y ninguno con este formato ha entrado nunca "
                        f"en la cuenta elegida. ¿Es de «{name}»?"
                    ),
                    account_id=other_id,
                    account_name=name,
                    total_rows=len(rows),
                )
            )

    hashes = _preview_row_hashes(rows, effective_mappings, user_id=user_id, currency=currency)
    if hashes:
        overlap = await accounts_holding_hashes(db, user_id, hashes, exclude_account_id=account_id)
        if overlap:
            other_id, matched = overlap[0]
            pct = matched * 100 / len(hashes)
            if pct > settings.import_cross_overlap_pct:
                name = await _name(other_id)
                warnings.append(
                    ImportWarning(
                        key=ImportWarningKey.ROWS_EXIST_IN_OTHER_ACCOUNT,
                        message=(
                            f"{matched} de las {len(hashes)} filas de este fichero ya "
                            f"existen en «{name}». ¿Lo importaste allí por error?"
                        ),
                        account_id=other_id,
                        account_name=name,
                        matched_rows=matched,
                        total_rows=len(hashes),
                    )
                )
    return warnings


async def run_commit(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    job_id: uuid.UUID,
    category_overrides: dict[str, uuid.UUID] | None = None,
    acknowledged_warnings: list[ImportWarningKey] | None = None,
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job no encontrado")
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
    # PHASE-47.A — los avisos de "esto parece de otra cuenta" se emiten en el
    # preview y hay que reconocerlos UNO A UNO para poder confirmar. Es un tick
    # explícito y no un banner: en julio de 2026 el import a la cuenta
    # equivocada no produjo ni un error, así que lo que faltaba no era más
    # información en pantalla, era una parada.
    acknowledged = {k.value for k in (acknowledged_warnings or [])}
    pending = [w for w in (payload_data.get("warnings") or []) if w.get("key") not in acknowledged]
    if pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    "Este fichero puede no ser de la cuenta elegida. "
                    "Revisa los avisos y confírmalos para continuar."
                ),
                "warnings": pending,
            },
        )

    rows_raw = payload_data.get("rows") or []
    effective_mappings = ImportColumnMappings.model_validate(payload_data["effective_mappings"])
    currency = payload_data.get("currency") or DEFAULT_CURRENCY
    default_category_id_raw = payload_data.get("default_category_id")
    default_category_id = uuid.UUID(default_category_id_raw) if default_category_id_raw else None
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
    # PHASE-37 (bugfix): NO aprendemos equivalencias para conceptos de
    # dirección ambigua en el lote (aparecen con cargo y abono) — evita
    # fijar un "BIZUM" → categoría de ingreso que luego mal-etiqueta pagos
    # salientes. El override sí se aplica a esta importación.
    valid_overrides: dict[str, uuid.UUID] = {}
    if category_overrides:
        ambiguous = _direction_ambiguous_concepts(rows_raw, effective_mappings)
        valid_overrides = await _persist_user_category_overrides(
            db, user_id, category_overrides, skip_learn=frozenset(ambiguous)
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


def _file_declares_signs(rows: list[dict[str, str]], mappings: ImportColumnMappings) -> bool:
    """PHASE-47.G — ¿este fichero expresa la dirección con el SIGNO del importe?

    `_parse_amount_signed` sólo llama «entrada» a un importe con `+` explícito,
    y un `33,58 €` a secas lo deja en «no declara dirección». Es lo correcto
    mirando UNA fila: hay extractos que son magnitudes puras y ahí la dirección
    la da el texto o la categoría.

    Pero mirando el FICHERO entero deja de ser cierto. Si alguna línea trae un
    cargo en negativo, ese banco expresa la dirección por el signo — y entonces
    un positivo desnudo no es un hueco, es un abono. Sin esta pregunta, las
    DEVOLUCIONES (un reembolso de Amazon, la anulación de un cobro) caían al
    kind de su categoría, que dice «compras», y entraban como gasto: el importe
    contado con el signo cambiado, o sea el doble de error que perderlo.

    Medido sobre los extractos reales del usuario: seis devoluciones entre abril
    y julio de 2026, 238,87 € que sumaban 477,74 € de desvío en el saldo. Las
    seis rompían la cadena `saldo ± importe` del propio extracto, que es la
    prueba independiente de que el signo estaba mal.
    """
    if not mappings.amount:
        return False
    for raw in rows:
        amount_raw = raw.get(mappings.amount, "")
        if not amount_raw:
            continue
        try:
            _amount, bank_sign = _parse_amount_signed(amount_raw)
        except (ArithmeticError, ValueError, _RowError):
            continue
        if bank_sign < 0:
            return True
    return False


def _direction_ambiguous_concepts(
    rows: list[dict[str, str]], mappings: ImportColumnMappings
) -> set[str]:
    """PHASE-37 (bugfix) — conceptos cuyo signo es AMBIGUO en el lote:
    aparecen con cargo (−) Y con abono (+).

    Un concepto así (p. ej. "BIZUM" pelado, que a veces sale y a veces
    entra) NO debe fijarse como una única equivalencia aprendida
    `concepto → categoría`: colapsaría la dirección y clasificaría un
    pago saliente en una categoría de ingreso (bug "Bizum recibido" con
    flow=OUT). Es la lección PHASE-32 generalizada al autoaprendizaje: la
    dirección se deriva del SIGNO del extracto (la verdad), no de una
    equivalencia fijada una vez.

    Se computa desde el signo del extracto por concepto normalizado (misma
    clave que usa `_persist_user_category_overrides` al aprender). Ámbito:
    el propio lote — que es donde el mapping venenoso se aprendió en el
    caso real (un extracto con BIZUM entrantes y salientes a la vez).
    """
    if not mappings.category_name or not mappings.amount:
        return set()
    signs_by_concept: dict[str, set[int]] = {}
    for raw in rows:
        concept_raw = raw.get(mappings.category_name, "")
        amount_raw = raw.get(mappings.amount, "")
        if not concept_raw or not amount_raw:
            continue
        normalized = normalize_concept(concept_raw)
        if not normalized:
            continue
        try:
            _amount, bank_sign = _parse_amount_signed(amount_raw)
        except (ArithmeticError, ValueError):
            continue
        if bank_sign != 0:
            signs_by_concept.setdefault(normalized, set()).add(bank_sign)
    return {concept for concept, seen in signs_by_concept.items() if len(seen) > 1}


async def _persist_user_category_overrides(
    db: AsyncSession,
    user_id: uuid.UUID,
    overrides: dict[str, uuid.UUID],
    *,
    skip_learn: frozenset[str] = frozenset(),
) -> dict[str, uuid.UUID]:
    """Valida que cada `category_id` pertenece al usuario y guarda la
    equivalencia (UPSERT). Devuelve los pares válidos con el concepto
    ya normalizado para que el caller los use al procesar filas.

    Conceptos con `category_id` ajeno se filtran silenciosamente —
    es un error del cliente, no del usuario, y no debe abortar la
    importación entera.

    PHASE-37 (bugfix): los conceptos en `skip_learn` (dirección ambigua en
    el lote, ver `_direction_ambiguous_concepts`) SÍ se devuelven en `valid`
    —el override del usuario se aplica en ESTA importación— pero NO se
    persisten como equivalencia aprendida, para no envenenar futuras
    importaciones con una dirección colapsada.
    """
    # Carga las categorías del usuario una vez para validar todas.
    user_cat_ids = {
        cat_id
        for (cat_id,) in (
            await db.execute(select(Category.id).where(Category.user_id == user_id))
        ).all()
    }

    valid: dict[str, uuid.UUID] = {}
    for raw_concept, cat_id in overrides.items():
        if cat_id not in user_cat_ids:
            continue
        normalized = normalize_concept(raw_concept)
        if not normalized:
            continue
        if normalized not in skip_learn:
            await upsert_bank_mapping(db, user_id, bank_concept=normalized, category_id=cat_id)
        valid[normalized] = cat_id
    return valid


# ─────────────────────────────────────────────────────────────────────────────
# Internals: procesamiento de filas (parse + dedup + reconcile + persistir)
# ─────────────────────────────────────────────────────────────────────────────


async def _load_transfer_categories(
    db: AsyncSession, user_id: uuid.UUID
) -> tuple[set[uuid.UUID], dict[CategoryKind, uuid.UUID]]:
    """PHASE-32 — Carga las categorías `is_transfer` del usuario.

    Devuelve (a) el set de sus ids y (b) un mapa `kind → id` con la más
    antigua de cada kind (misma elección que
    `get_or_create_default_transfer_category`). Sirve para forzar la
    dirección correcta al importar: una transferencia cuya descripción
    dice "RECIBIDA" debe quedar en la categoría de transferencia INCOME
    aunque un bank-mapping aprendido apunte a la de EXPENSE (y al revés).
    No crea nada: si el usuario no tiene la categoría del kind necesario,
    el caller deja la resuelta tal cual.
    """
    rows = (
        await db.execute(
            select(Category.id, Category.kind)
            .where(Category.user_id == user_id)
            .where(Category.is_transfer.is_(True))
            .order_by(Category.created_at.asc())
        )
    ).all()
    ids: set[uuid.UUID] = set()
    by_kind: dict[CategoryKind, uuid.UUID] = {}
    for cat_id, kind in rows:
        ids.add(cat_id)
        by_kind.setdefault(kind, cat_id)
    return ids, by_kind


def _bank_signed_amount(p: ParsedRow) -> Decimal | None:
    """Movimiento con el signo del BANCO (no el de la app): entrada suma,
    salida resta. `None` si el flow quedó sin clasificar. Se usa sólo para
    validar la cadena saldo±importe del extracto (PHASE-39)."""
    if p.flow in (TransactionFlow.IN, TransactionFlow.TRANSFER_IN):
        return p.amount
    if p.flow in (TransactionFlow.OUT, TransactionFlow.TRANSFER_OUT):
        return -p.amount
    return None


def _chain_matches(rows: list[ParsedRow], *, newest_first: bool) -> int:
    """Cuántos pares consecutivos satisfacen la aritmética de la cadena de
    saldos del extracto bajo la hipótesis de orden dada.

    - newest-first (fila i es POSTERIOR a la i+1):
        saldo[i] == saldo[i+1] + movimiento[i]
    - oldest-first (fila i es ANTERIOR a la i+1):
        saldo[i+1] == saldo[i] + movimiento[i+1]

    Pares sin saldo o sin movimiento clasificable no puntúan.
    """
    matches = 0
    for a, b in itertools.pairwise(rows):
        if a.statement_balance is None or b.statement_balance is None:
            continue
        if newest_first:
            moved = _bank_signed_amount(a)
            if moved is not None and a.statement_balance == b.statement_balance + moved:
                matches += 1
        else:
            moved = _bank_signed_amount(b)
            if moved is not None and b.statement_balance == a.statement_balance + moved:
                matches += 1
    return matches


def _rows_oldest_first(rows: list[ParsedRow]) -> list[ParsedRow]:
    """Las filas CON saldo, ordenadas de la más antigua a la más reciente.

    El orden se deduce igual que en `_pick_balance_anchor` —por las fechas de
    la primera y la última, y con la aritmética de la cadena como desempate
    cuando el extracto es de un solo día—. No se ordena por fecha: dentro de un
    mismo día el extracto imprime en un orden que las fechas no capturan, y es
    ESE orden el que hace que la cadena de saldos cuadre.
    """
    with_balance = [p for p in rows if p.statement_balance is not None]
    if len(with_balance) < 2:
        return with_balance
    first, last = with_balance[0], with_balance[-1]
    if first.occurred_at > last.occurred_at:
        newest_first = True
    elif first.occurred_at < last.occurred_at:
        newest_first = False
    else:
        newest_first = _chain_matches(with_balance, newest_first=True) >= _chain_matches(
            with_balance, newest_first=False
        )
    return list(reversed(with_balance)) if newest_first else with_balance


class ChainOutcome(NamedTuple):
    """Qué hizo la cadena de saldos: huecos rellenados y direcciones corregidas."""

    resolved: int
    corrected: int


def resolve_flows_from_balance_chain(rows: list[ParsedRow]) -> ChainOutcome:
    """La dirección la manda el SALDO del extracto, no la conjetura.

    **Por qué existe.** La dirección se venía deduciendo del signo del importe,
    y si no del texto, y si no del kind de la categoría. Son tres señales que
    DESCRIBEN el movimiento; ninguna lo demuestra, y las tres han fallado ya
    (PHASE-28, 32, 34, 37, 38, 46, 47.F, 47.G — la misma familia nueve veces).
    El salto del saldo sí lo demuestra: `saldo_anterior ± importe = saldo` es
    aritmética, no interpretación, y le da igual cómo redacte el banco.

    **PHASE-47.G — y por eso manda, en vez de rellenar huecos.** Hasta aquí
    esto sólo tocaba las filas que se habían quedado SIN dirección. Una
    conjetura que acertaba a decidir —mal— nunca llegaba a contrastarse: seis
    devoluciones de abril a julio de 2026 entraron como gasto, 238,87 € con el
    signo cambiado, y las seis rompían la cadena de su propio extracto. Ahora,
    cuando el extracto contradice a la conjetura, gana el extracto.

    **Por qué es seguro.** Se exige que el salto entre dos saldos consecutivos
    sea EXACTAMENTE el importe de la fila. Si entre ambas hubiera otro
    movimiento sin saldo, el salto no cuadraría y no se toca nada: mejor una
    fila neutra —o incluso una conjetura— que una dirección inventada a partir
    de un salto que no cuadra. Y la fila vuelve a pasar por
    `classify_import_flow` con el signo deducido, así que su transfer-ness se
    decide con la misma regla que el resto y no con una copia.

    Sólo gobierna la DIRECCIÓN. Si la cadena confirma el sentido que ya tenía,
    no se toca nada aunque la transfer-ness difiera: eso lo decide el texto, y
    el saldo no sabe nada de eso.
    """
    ordered = _rows_oldest_first(rows)
    resolved = 0
    corrected = 0
    for previous, current in itertools.pairwise(ordered):
        assert previous.statement_balance is not None  # `_rows_oldest_first` filtra
        assert current.statement_balance is not None
        delta = current.statement_balance - previous.statement_balance
        if abs(delta) != current.amount or delta == 0:
            continue
        already = _bank_signed_amount(current)
        if already is not None and (already > 0) == (delta > 0):
            continue  # el extracto confirma lo que la fila ya decía
        flow = classify_import_flow(
            bank_sign=1 if delta > 0 else -1,
            text=current.classify_text,
            category_is_transfer=current.category_is_transfer,
        )
        if flow is None:
            continue
        if already is None:
            resolved += 1
        else:
            corrected += 1
        current.flow = flow
    return ChainOutcome(resolved=resolved, corrected=corrected)


def _pick_balance_anchor(rows: list[ParsedRow]) -> tuple[datetime, Decimal] | None:
    """PHASE-39 — elige el ancla de saldo del lote: `(fecha, saldo)` del
    movimiento CRONOLÓGICAMENTE más reciente que trae saldo de extracto.

    Los parsers preservan el orden del fichero, pero cada banco imprime en
    una dirección (BBVA: más reciente arriba). La dirección se detecta por
    las fechas de la primera y última fila con saldo; si empatan (extracto
    de un solo día), se valida la aritmética de la cadena saldo±importe en
    ambas hipótesis y gana la que más pares satisface (empate → newest-first,
    el formato dominante en bancos españoles).
    """
    cands = [p for p in rows if p.statement_balance is not None]
    if not cands:
        return None
    first, last = cands[0], cands[-1]
    if first.occurred_at > last.occurred_at:
        newest_first = True
    elif first.occurred_at < last.occurred_at:
        newest_first = False
    else:
        newest_first = _chain_matches(cands, newest_first=True) >= _chain_matches(
            cands, newest_first=False
        )
    max_date = max(p.occurred_at for p in cands)
    same_day = [p for p in cands if p.occurred_at == max_date]
    anchor = same_day[0] if newest_first else same_day[-1]
    assert anchor.statement_balance is not None  # filtrado arriba
    return anchor.occurred_at, anchor.statement_balance


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
    # AUDIT finding #1: necesitamos el kind de cada categoría para
    # validar la dirección de la fila contra el signo del extracto, y un
    # mapa nombre+kind para reasignar a la categoría hermana en caso de
    # contradicción.
    category_kinds, sibling_by_name_kind = await _build_category_kinds(db, user_id)

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

    # PHASE-32 — la dirección de una transferencia la decide SIEMPRE la
    # descripción (RECIBIDA/REALIZADA…), no la equivalencia aprendida. Un
    # cobro mal aprendido como "Transferencias (gasto)" restaría del saldo
    # en lugar de sumar (bug reportado: BBVA a 0 con ingreso neto).
    transfer_cat_ids, transfer_by_kind = await _load_transfer_categories(db, user_id)

    parsed: list[ParsedRow] = []
    errors: list[dict[str, object]] = []
    # AUDIT-2026-07 (LOW): contador de fallos INDEPENDIENTE del log topado a
    # MAX_ERROR_LOG. Antes `rows_failed = len(errors)` reportaba como mucho 100
    # aunque hubiera más filas erróneas, y los contadores del job no cuadraban
    # con rows_total. El detalle se sigue topando; el recuento no.
    failed_count = 0
    # AUDIT finding #1: filas cuyo signo de extracto contradice el kind
    # de la categoría resuelta y NO tienen categoría hermana del kind
    # correcto. Se persisten igual (no perdemos datos), pero se marcan en
    # el error_log con `"review": True` para que el preview avise al
    # usuario en lugar de guardar un signo erróneo en silencio.
    review: list[dict[str, object]] = []

    # Se pregunta UNA vez por lote: la convención de signos es del fichero.
    declares_signs = _file_declares_signs(rows, effective_mappings)

    for idx, raw in enumerate(rows, start=1):
        try:
            parsed_row, review_note = _parse_row(
                raw,
                mappings=effective_mappings,
                user_id=user_id,
                currency=currency.upper(),
                category_lookup=category_lookup,
                default_category_id=default_category_id,
                bank_mappings=saved_mappings,
                rules=rules,
                transfer_cat_ids=transfer_cat_ids,
                transfer_by_kind=transfer_by_kind,
                category_kinds=category_kinds,
                sibling_by_name_kind=sibling_by_name_kind,
                file_declares_signs=declares_signs,
            )
        except _RowError as e:
            failed_count += 1
            if len(errors) < MAX_ERROR_LOG:
                errors.append({"row": idx, "error": str(e)})
            continue
        if review_note is not None and len(review) < MAX_ERROR_LOG:
            review.append({"row": idx, "error": review_note, "review": True})
        parsed.append(parsed_row)

    # PHASE-46/47.G: segunda pasada con la columna Saldo, que es la ÚNICA
    # prueba aritmética de la dirección. Va aquí y no dentro del bucle porque el
    # salto de saldo es una relación ENTRE filas consecutivas: mirando una sola
    # no se puede saber. Rellena las filas sin dirección y CORRIGE las que la
    # tengan al revés.
    chain = resolve_flows_from_balance_chain(parsed)
    if chain.resolved and len(review) < MAX_ERROR_LOG:
        plural = "movimiento" if chain.resolved == 1 else "movimientos"
        review.append(
            {
                "row": 0,
                "error": (
                    f"{chain.resolved} {plural} sin signo en el extracto: la "
                    "dirección se ha deducido del salto de la columna Saldo. "
                    "Compruébalos antes de confirmar."
                ),
                "review": True,
            }
        )
    if chain.corrected and len(review) < MAX_ERROR_LOG:
        plural = "movimiento" if chain.corrected == 1 else "movimientos"
        review.append(
            {
                "row": 0,
                "error": (
                    f"{chain.corrected} {plural} entraban con la dirección al revés "
                    "(típicamente una devolución leída como gasto): la columna Saldo "
                    "del extracto dice lo contrario y manda ella."
                ),
                "review": True,
            }
        )

    # AUDIT finding #2: asigna un ordinal de ocurrencia DENTRO del lote a
    # cada grupo de filas con el mismo hash base (user+amount+currency+
    # date+desc). La primera ocurrencia conserva el hash histórico
    # (occurrence=0); la 2ª, 3ª... reciben hashes derivados distintos. Así
    # dos líneas legítimas idénticas el mismo día NO colapsan, pero
    # re-importar el mismo fichero sigue siendo idempotente (mismas filas,
    # mismo orden → mismos ordinales → mismos hashes).
    occurrence_counter: dict[str, int] = {}
    for p in parsed:
        base = p.import_hash
        occ = occurrence_counter.get(base, 0)
        occurrence_counter[base] = occ + 1
        if occ:
            p.import_hash = _compute_hash(
                user_id=user_id,
                amount=p.amount,
                currency=currency.upper(),
                occurred_at=p.occurred_at,
                description=p.description,
                occurrence=occ,
            )

    # Tras asignar ordinales, dos filas idénticas tienen hashes distintos,
    # así que este paso ya sólo elimina re-procesos defensivos (no debería
    # quitar filas legítimas). Se mantiene por robustez frente a hashes
    # repetidos inesperados.
    seen_hashes_in_batch: set[str] = set()
    deduped: list[ParsedRow] = []
    for p in parsed:
        if p.import_hash in seen_hashes_in_batch:
            continue
        seen_hashes_in_batch.add(p.import_hash)
        deduped.append(p)

    existing = await find_existing_hashes(db, user_id, [p.import_hash for p in deduped])
    skipped_in_batch = len(parsed) - len(deduped)

    # AUDIT-2026-05: comprueba UNA vez si la cuenta tiene `expected`
    # pendientes. El caso común (ninguna) se saltaba con N queries
    # vacías — una por fila. Con esto sólo reconciliamos si hace falta.
    #
    # Trade-off consciente (P2): si un proceso concurrente (cron de
    # autopost) inserta un `expected` DESPUÉS de este check pero antes de
    # terminar el import, esa fila no se reconcilia en este lote y puede
    # crear un duplicado. El peor caso es un duplicado que el usuario
    # reconcilia a mano — no hay pérdida de datos ni cálculo erróneo — y
    # la ventana es de microsegundos. El código previo (reconcile por
    # fila) tenía la misma carrera a grano más fino. Aceptable para un
    # host único de dev; revisitar si se pasa a multi-worker.
    try_reconcile = await has_pending_expected(db, user_id, account_id)

    reconciled = 0
    # AUDIT finding #3: con `autoflush=False` y sin flush en el bucle, dos
    # filas distintas del mismo importe/fecha/descripción podían reconciliar
    # AMBAS contra la misma tx `expected` (la query de
    # `reconcile_with_expected` filtra por `import_hash IS NULL` pero el
    # primer match sólo muta el objeto EN MEMORIA — sin flush la BD sigue
    # viéndola sin conciliar). La segunda fila reconciliaba en vez de
    # insertarse → se perdía una tx real. Fix robusto: el caller lleva el
    # set de ids ya consumidos en este lote, ignora un match repetido (cae
    # a inserción), y hace `flush()` tras cada match para que la siguiente
    # query ya no vea la `expected` consumida.
    consumed_expected_ids: set[uuid.UUID] = set()
    pending_inserts: list[ParsedRow] = []
    for p in deduped:
        if p.import_hash in existing:
            continue
        # PHASE-17.3: si una tx `expected` casa con esta fila, en
        # lugar de crear duplicada le asignamos el `import_hash` y
        # actualizamos su descripción. Cuenta como reconciliación,
        # no como inserción.
        match = (
            await reconcile_with_expected(
                db,
                user_id,
                account_id=account_id,
                occurred_at=p.occurred_at,
                amount=p.amount,
                currency=currency.upper(),
                description=p.description,
                import_hash=p.import_hash,
            )
            if try_reconcile
            else None
        )
        if match is not None and match.id not in consumed_expected_ids:
            consumed_expected_ids.add(match.id)
            # Flush para que el `import_hash` recién asignado sea visible a
            # la query de la siguiente fila (evita doble-match — finding #3).
            await db.flush()
            reconciled += 1
            continue
        # Si el match repite una `expected` ya consumida en este lote, lo
        # tratamos como NO-match y caemos a inserción: dos filas reales no
        # deben colapsar en una sola `expected`.
        pending_inserts.append(p)

    # PHASE-47.E1: un recibo de tarjeta llega escrito de varias formas y con
    # fechas distintas. Se queda una copia y las demás se descartan. No se
    # suman a `skipped_in_batch`: `skipped_existing` se DERIVA de lo que entra
    # menos lo que se inserta, así que ya las cuenta — sumarlas las contaría
    # dos veces en el resumen que ve el usuario.
    pending_inserts, _duplicate_settlements = await _drop_duplicate_settlements(
        db, user_id, account_id, pending_inserts
    )

    inserted = await _flush_inserts(
        db,
        pending_inserts,
        user_id=user_id,
        account_id=account_id,
        currency=currency.upper(),
        existing=existing,
    )

    skipped_existing = len(deduped) - inserted - reconciled

    # PHASE-39 — backfill del saldo del extracto en filas YA existentes
    # (duplicadas por hash o reconciliadas contra `expected`). Un reimport
    # del mismo fichero se salta las filas (dedup) pero SÍ enriquece las tx
    # existentes con el saldo si aún no lo tenían — así reimportar el
    # histórico rellena `statement_balance` sin duplicar nada. El filtro
    # `IS NULL` hace la operación idempotente y no pisa valores previos.
    balance_by_hash = {
        p.import_hash: p.statement_balance for p in deduped if p.statement_balance is not None
    }
    for import_hash, balance in balance_by_hash.items():
        await db.execute(
            update(Transaction)
            .where(Transaction.user_id == user_id)
            .where(Transaction.import_hash == import_hash)
            .where(Transaction.deleted_at.is_(None))
            .where(Transaction.statement_balance.is_(None))
            .values(statement_balance=balance)
        )

    job.rows_ok = inserted + reconciled
    job.rows_failed = failed_count
    job.rows_skipped = skipped_in_batch + skipped_existing
    # AUDIT finding #1: adjuntamos las advertencias de revisión (signo de
    # extracto vs. kind sin categoría hermana) al error_log para que el
    # preview las muestre. No cuentan como filas fallidas — la tx se
    # persiste igual; el usuario decide si corrige la categoría.
    job.error_log = errors + review
    job.status = ImportJobStatus.COMPLETED

    # PHASE-39 — auto-anclaje del saldo real: si el extracto trae columna
    # Saldo, anclamos el `opening_balance` de la cuenta al saldo del
    # movimiento más reciente del fichero (misma semántica que "Cuadrar
    # saldo", a la fecha del extracto). Best-effort: las guardas (cuenta
    # no-ASSET, divisa distinta, ancla más reciente ya existente) lo
    # saltan sin afectar al import.
    anchored: dict[str, str] | None = None
    anchor = _pick_balance_anchor(deduped)
    if anchor is not None:
        anchor_at, anchor_balance = anchor
        anchored = await anchor_account_balance_at(
            db,
            user_id,
            account_id,
            balance=anchor_balance,
            at=anchor_at,
            currency=currency.upper(),
        )
    if anchored is not None:
        # Reasignación completa (no mutación in-place): la columna JSON
        # sólo detecta cambios cuando se asigna un objeto nuevo.
        job.preview_payload = {**(job.preview_payload or {}), "balance_anchor": anchored}
    elif inserted + reconciled > 0:
        # El lote NO ancló (sin columna Saldo, o su ancla es más antigua
        # que la existente) pero SÍ añadió movimientos. Si son anteriores
        # a la fecha del ancla persistida, la Σmov(≤ancla) cambió y el
        # opening quedaría desviado exactamente en la suma de esas filas.
        # Re-derivamos desde el ancla guardada para preservar
        # `saldo(fecha_ancla) == saldo_extracto` (no-op si nunca se ancló).
        await re_anchor_from_stored(db, user_id, account_id)

    await db.flush()
    await db.refresh(job)


def _settlement_preference(p: ParsedRow) -> tuple[int, int, int, str, str]:
    """Orden de preferencia entre copias del MISMO recibo. Menor gana.

    Cuando el mismo hecho llega escrito de varias formas, sobrevive la copia
    que MÁS dice: la que el clasificador entendió (tiene dirección), la que
    resolvió categoría, y la de texto más largo — que es la que trae el número
    de tarjeta y permite saber de cuál se trata. La fecha y el hash cierran el
    desempate para que el resultado no dependa del orden del fichero.
    """
    return (
        0 if p.flow is not None else 1,
        0 if p.category_id is not None else 1,
        -len(p.description or ""),
        p.occurred_at.isoformat(),
        p.import_hash,
    )


def _same_direction(left: TransactionFlow | None, right: TransactionFlow | None) -> bool:
    """¿Los dos movimientos van en el mismo sentido?

    `amount` guarda la MAGNITUD sin signo y el signo vive en `flow` (ADR-0004),
    así que sin esta comprobación un cargo y su devolución —mismo importe,
    mismos días, y las dos redacciones casan con la secuencia de liquidación—
    serían indistinguibles, y la devolución se perdería tomada por una copia.

    Una dirección desconocida (`None`) sólo casa con otra desconocida: es lo
    que hace el extracto sin signos, y ahí preferimos insertar de más —el
    usuario ve la fila y decide— antes que borrar un movimiento real.
    """
    if left is None or right is None:
        return left is None and right is None
    return left == right


async def _drop_duplicate_settlements(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    pending: list[ParsedRow],
) -> tuple[list[ParsedRow], int]:
    """Deja UNA fila por recibo de tarjeta y descarta las copias.

    El banco escribe el mismo recibo con dos redacciones y las fecha distinto,
    y el extracto de la cuenta y el de la tarjeta lo traen los dos. Medido en
    la BD del usuario: entre 2 y 4 filas por ciclo para un único cobro, todos
    los meses, que él venía borrando a mano.

    Compara contra lo que ya está persistido Y contra lo que va en este mismo
    lote, porque las copias llegan por las dos vías. El `import_hash` no puede
    hacer este trabajo: cambia con el texto y con la fecha, que es justo lo que
    difiere entre las copias.

    No se toca nada que no sea una liquidación: el resto de filas pasa entero.
    """
    settlements = [p for p in pending if is_card_settlement(p.description)]
    if not settlements:
        return pending, 0

    window = timedelta(days=SETTLEMENT_DUPLICATE_WINDOW_DAYS)
    dates = [p.occurred_at for p in settlements]
    persisted = await find_live_card_settlements(
        db,
        user_id,
        account_id,
        since=min(dates) - window,
        until=max(dates) + window,
    )

    # La regla se enuncia en DÍAS, así que se compara por fecha de calendario.
    # Lo que llega del parser es naive y lo que devuelve la BD es aware
    # (`TIMESTAMPTZ`); restarlos directamente revienta, y forzar una zona sería
    # inventar una precisión que la regla no usa.
    claimed = [(d.date(), a, f) for d, a, f in persisted]

    dropped: set[str] = set()
    for p in sorted(settlements, key=_settlement_preference):
        day = p.occurred_at.date()
        if any(
            a == p.amount and _same_direction(f, p.flow) and abs(d - day) <= window
            for d, a, f in claimed
        ):
            dropped.add(p.import_hash)
            continue
        claimed.append((day, p.amount, p.flow))

    if not dropped:
        return pending, 0
    # Se reconstruye en el ORDEN original: el descarte no debe reordenar el
    # lote, que es lo que lee la cadena de saldos.
    return [p for p in pending if p.import_hash not in dropped], len(dropped)


async def _flush_inserts(
    db: AsyncSession,
    rows: list[ParsedRow],
    *,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    currency: str,
    existing: set[str],
) -> int:
    """Persiste las filas a insertar y devuelve cuántas se insertaron.

    AUDIT finding #6 — manejo defensivo de `IntegrityError`. Camino rápido:
    bulk-add + UN flush (comportamiento histórico, sin coste por fila).
    Sólo si ese flush colisiona con el índice parcial único
    (user_id, import_hash) — posible si un proceso concurrente insertó la
    misma fila entre nuestro `find_existing_hashes` y este flush — se hace
    rollback del flush fallido y se reintenta fila a fila dentro de
    SAVEPOINTs (`begin_nested`): cada colisión se trata como
    "ya existe → skipped" en lugar de propagar un 500, y las filas sanas
    del lote se conservan. Carrera consciente y rara (mismo fichero
    importado en paralelo); resolución defensiva sin locks complejos.
    """
    if not rows:
        return 0

    def _new_tx(p: ParsedRow) -> Transaction:
        return Transaction(
            user_id=user_id,
            account_id=account_id,
            category_id=p.category_id,
            amount=p.amount,
            currency=currency,
            occurred_at=p.occurred_at,
            description=p.description,
            source=TransactionSource.IMPORT,
            import_hash=p.import_hash,
            flow=p.flow,
            statement_balance=p.statement_balance,
        )

    # Camino rápido: añade todo y flush una vez.
    try:
        async with db.begin_nested():
            db.add_all([_new_tx(p) for p in rows])
        return len(rows)
    except IntegrityError:
        # El flush en bloque falló por una colisión. Reintentamos fila a
        # fila para aislar la(s) culpable(s) y conservar el resto.
        pass

    inserted = 0
    for p in rows:
        if p.import_hash in existing:
            continue
        try:
            async with db.begin_nested():
                db.add(_new_tx(p))
            existing.add(p.import_hash)
            inserted += 1
        except IntegrityError:
            existing.add(p.import_hash)
            continue
    return inserted


async def get_ai_suggestions(
    db: AsyncSession,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
) -> dict[str, uuid.UUID | None]:
    """Para un job en PREVIEW, pide al modelo de texto local que sugiera
    categorías para los conceptos del banco aún sin sugerencia (sin
    mapping guardado ni regla matching).

    AUDIT-2026-05: lógica movida del router (`router.py` ai_suggest) al
    service. No persiste nada — el caller devuelve las sugerencias para
    que el usuario confirme; al commit se guardan las aceptadas como
    `bank_category_mappings`. Devuelve `{concepto_normalizado: cat_id |
    None}`. Lanza `HTTPException` si el job no existe, no está en PREVIEW
    o no tiene filas (mismos contratos que el endpoint previo).
    """
    job = await get_job_by_id(db, job_id, user_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job no encontrado")
    if job.status != ImportJobStatus.PREVIEW:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job en estado {job.status.value}, no se puede sugerir",
        )
    if not job.preview_payload:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job sin filas")

    payload_data = job.preview_payload
    rows_raw = payload_data.get("rows") or []
    effective_mappings = ImportColumnMappings.model_validate(payload_data["effective_mappings"])
    if not effective_mappings.category_name:
        return {}

    # Detecta los conceptos únicos sin sugerencia previa: ni mapping
    # exacto ni regla matching para todas las filas del grupo.
    saved_mappings = await get_mappings_for_concepts(
        db,
        user_id,
        [str(r.get(effective_mappings.category_name) or "") for r in rows_raw],
    )
    rules = await list_rules_for_user(db, user_id, enabled_only=True)

    rows_by_concept: dict[str, list[tuple[str, str | None]]] = {}
    display_by_concept: dict[str, str] = {}
    for raw in rows_raw:
        cell = str(raw.get(effective_mappings.category_name) or "").strip()
        if not cell:
            continue
        norm = normalize_concept(cell)
        if norm not in rows_by_concept:
            rows_by_concept[norm] = []
            display_by_concept[norm] = cell
        description = (
            str(raw.get(effective_mappings.description) or "").strip()
            if effective_mappings.description
            else ""
        ) or None
        rows_by_concept[norm].append((cell, description))

    pending: list[dict[str, str]] = []
    for norm, rows_in_group in rows_by_concept.items():
        if norm in saved_mappings:
            continue
        if rules:
            resolved = {
                find_first_matching_rule(rules, concept=concept, description=description)
                for concept, description in rows_in_group
            }
            cat_ids = {r.category_id for r in resolved if r is not None}
            if len(cat_ids) == 1 and len(resolved) == 1:
                # Ya hay sugerencia por regla — no necesita IA.
                continue
        # Sin sugerencia previa: candidato para IA. Mando concepto + la
        # primera description del grupo como ejemplo.
        first_desc = next((d for _, d in rows_in_group if d), "")
        pending.append(
            {
                "id": norm,
                "concept": display_by_concept[norm],
                "description": first_desc or "",
            }
        )

    if not pending:
        return {}

    cats_q = await db.execute(
        select(Category).where(Category.user_id == user_id).order_by(Category.name)
    )
    cats = list(cats_q.scalars().all())
    cat_payload = [
        {
            "id": str(c.id),
            "name": c.name,
            "kind": "ingreso" if c.kind.value == "income" else "gasto",
        }
        for c in cats
    ]

    try:
        ai_result = await ai_service.suggest_categories_for_concepts(pending, cat_payload)
    except AiError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"IA: {e}") from e

    suggestions: dict[str, uuid.UUID | None] = {}
    for concept_norm, cat_id_str in ai_result.items():
        if cat_id_str is None:
            suggestions[concept_norm] = None
            continue
        try:
            suggestions[concept_norm] = uuid.UUID(cat_id_str)
        except ValueError:
            suggestions[concept_norm] = None
    return suggestions


async def _mark_job_failed(db: AsyncSession, job: ImportJob, error: str) -> ImportJob:
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
) -> tuple[list[dict[str, str]], ImportColumnMappings, ImportSource, list[str] | None]:
    """Pipeline de parseo con cascada de fallbacks.

    El cuarto elemento es la **cabecera REAL del fichero**, o `None` cuando no
    la hay (visión: el modelo devuelve estructura, no columnas). Viaja aparte
    porque los dos smart-parsers emiten filas con claves FIJAS por contrato
    (`SMART_FORCED_MAPPING`), así que `rows[0].keys()` es la misma constante
    para cualquier fichero de cualquier banco — y el guardarraíl de PHASE-47.A,
    que compara formatos, no discriminaría nada. En los caminos legacy y CSV la
    cabecera SÍ son las claves, porque `parse_file` indexa por ella.

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
        rows = await asyncio.to_thread(parse_file, payload, filename, content_type)
        return rows, mappings, ImportSource.CSV, _keys_of(rows)
    if fmt == "xlsx":
        # Intentamos primero el smart parser (mismo enfoque que PDF):
        # detecta roles de columnas automáticamente y produce filas con
        # `category_name` para que el preview agrupe por concepto del
        # banco y dispare el autocompletado de categorías. Si la
        # heurística no es confiable (cabeceras raras, columnas críticas
        # ausentes), caemos al `parse_xlsx` legacy con el mapping del
        # usuario — comportamiento histórico.
        try:
            rows, header = await asyncio.to_thread(parse_xlsx_smart, payload)
            return rows, SMART_FORCED_MAPPING, ImportSource.XLSX_SMART, header
        except SmartParseAmbiguousError:
            rows = await asyncio.to_thread(parse_file, payload, filename, content_type)
            return rows, mappings, ImportSource.XLSX, _keys_of(rows)

    # PDF
    if force_vision:
        rows = await _parse_pdf_with_vision(payload)
        # Visión no lee columnas: no hay cabecera que comparar.
        return rows, VISION_FORCED_MAPPING, ImportSource.VISION, None

    try:
        rows, header = await asyncio.to_thread(parse_pdf_smart, payload)
        return rows, SMART_FORCED_MAPPING, ImportSource.PDFPLUMBER_SMART, header
    except NoTablesInPdfError:
        rows = await _parse_pdf_with_vision(payload)
        return rows, VISION_FORCED_MAPPING, ImportSource.VISION, None
    except SmartParseAmbiguousError:
        # Heurística no encontró una tabla clara: caemos al legacy
        # parser que concatena todas las tablas y deja al usuario
        # mapear las columnas a mano (comportamiento histórico).
        rows = await asyncio.to_thread(parse_file, payload, filename, content_type)
        return rows, mappings, ImportSource.PDFPLUMBER_LEGACY, _keys_of(rows)


def _keys_of(rows: list[dict[str, str]]) -> list[str] | None:
    """Cabecera de un lote parseado por `parse_file`, que indexa por ella."""
    return list(rows[0].keys()) if rows else None


async def _parse_pdf_with_vision(payload: bytes) -> list[dict[str, str]]:
    """Renderiza el PDF a imágenes y las pasa al modelo de visión.

    Devuelve filas con las keys fijas `amount`, `occurred_at`, `description`
    para que el resto del pipeline las trate igual que las parseadas con
    `parse_file`.

    Limita a `MAX_VISION_PDF_PAGES` páginas: la inferencia es cara y los
    extractos típicos rara vez tienen más de 3-4 páginas relevantes.

    AUDIT-2026-07 (M-04): si el PDF excede ese tope, se ABORTA con un mensaje
    accionable en lugar de importar sólo las primeras páginas y reportar éxito
    (pérdida silenciosa de las transacciones de las páginas posteriores).
    """
    total_pages = count_pdf_pages(payload)
    if total_pages > MAX_VISION_PDF_PAGES:
        raise ParseError(
            f"El PDF tiene {total_pages} páginas y el reconocimiento por visión "
            f"local está limitado a {MAX_VISION_PDF_PAGES}. Para no perder "
            f"transacciones, divide el extracto en partes de {MAX_VISION_PDF_PAGES} "
            f"páginas o menos y vuelve a importarlas."
        )
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
    transfer_cat_ids: set[uuid.UUID] | None = None,
    transfer_by_kind: dict[CategoryKind, uuid.UUID] | None = None,
    category_kinds: dict[uuid.UUID, CategoryKind] | None = None,
    sibling_by_name_kind: dict[tuple[str, CategoryKind], uuid.UUID] | None = None,
    file_declares_signs: bool = False,
) -> tuple[ParsedRow, str | None]:
    """Aplica mapping + validación + hash a una fila.

    Devuelve `(ParsedRow, review_note)`. `review_note` es `None` salvo que
    haya que corregir la dirección y no exista categoría hermana del kind
    correcto: (a) categoría normal cuyo kind contradice el signo del
    extracto (AUDIT finding #1), o (b) categoría de transferencia cuya
    dirección (texto o signo) contradice su kind y falta la transfer
    hermana del kind correcto (PHASE-32 HIGH#4). En ambos casos es un
    mensaje para marcar la fila para revisión en el preview.

    Prioridad para `category_id` (de mayor a menor):
    1. `bank_mappings[concepto_normalizado]` — equivalencia explícita
       del usuario (override actual o aprendida de imports previos).
    2. Match exacto en `category_lookup` por nombre case-insensitive.
    3. `rules` (PHASE-20) — primera regla habilitada que matchea por
       prioridad. Evalúa contra `concept` (category_name del banco) y
       `description` según el `field` de cada regla.
    4. `default_category_id` del usuario al subir el fichero.
    5. `None` (transacción sin categoría).

    Corrección de dirección (lección PHASE-28/31/32 — la dirección NUNCA
    se infiere de `category.kind`, se deriva del SIGNO del extracto o del
    texto):
    - Si la categoría es `is_transfer`, la dirección la decide el texto
      (RECIBIDA/REALIZADA); si el texto no decide, el SIGNO del extracto
      (PHASE-32 HIGH#5 — muchos bancos no llevan esas palabras). Sólo se
      reasigna a la hermana si el kind ACTUAL de la categoría resuelta NO
      coincide con la dirección inferida (AUDIT finding #5: antes
      reasignaba siempre a la `is_transfer` más antigua del kind,
      descartando la categoría específica correcta). Si falta la transfer
      hermana del kind correcto, se marca la fila para revisión en vez de
      persistir el signo invertido (PHASE-32 HIGH#4).
    - Para categorías normales, si el extracto trae el importe FIRMADO
      (cargo `-` / abono `+`), ese signo es la verdad sobre la dirección.
      Si contradice el kind de la categoría resuelta, se reasigna a una
      categoría con el mismo nombre y el kind correcto (hermana); si no
      existe, se deja la resuelta y se marca la fila para revisión
      (AUDIT finding #1) — nunca se persiste un signo erróneo en silencio.
    """
    amount_raw = raw.get(mappings.amount, "").strip()
    occurred_raw = raw.get(mappings.occurred_at, "").strip()
    description_raw = raw.get(mappings.description, "").strip() if mappings.description else ""
    category_name_raw = (
        raw.get(mappings.category_name, "").strip() if mappings.category_name else ""
    )
    # PHASE-39 — columna Saldo (opcional, tolerante: nunca tumba la fila).
    balance_raw = (
        raw.get(mappings.statement_balance, "").strip() if mappings.statement_balance else ""
    )

    if not amount_raw:
        raise _RowError(f"columna '{mappings.amount}' vacía")
    if not occurred_raw:
        raise _RowError(f"columna '{mappings.occurred_at}' vacía")

    amount, bank_sign = _parse_amount_signed(amount_raw)
    # Un positivo desnudo sólo significa «entrada» si este fichero expresa la
    # dirección con el signo, cosa que se sabe mirando el LOTE y no la fila
    # (ver `_file_declares_signs`). Sin esto, una devolución entraba como gasto.
    if bank_sign == 0 and file_declares_signs:
        bank_sign = 1
    occurred_at = _parse_datetime(occurred_raw)
    description = description_raw or None

    category_id: uuid.UUID | None = default_category_id
    resolved_name: str | None = None
    matched = False
    if category_name_raw:
        normalized = category_name_raw.casefold().strip()
        if bank_mappings is not None and normalized in bank_mappings:
            category_id = bank_mappings[normalized]
            matched = True
        elif (cat_match := category_lookup.get(normalized)) is not None:
            category_id = cat_match
            resolved_name = normalized
            matched = True
    if not matched and rules:
        rule = find_first_matching_rule(
            rules, concept=category_name_raw or None, description=description
        )
        if rule is not None:
            category_id = rule.category_id

    review_note: str | None = None

    # Dirección de TRANSFERENCIAS — el signo lo manda el texto
    # (RECIBIDA/REALIZADA), no la equivalencia aprendida. AUDIT finding #5:
    # sólo reasignar si el kind actual de la categoría resuelta NO coincide
    # con la dirección inferida; si ya coincide, dejar la categoría
    # específica que se resolvió (no degradar a la `is_transfer` más
    # antigua del kind).
    if (
        category_id is not None
        and transfer_cat_ids
        and transfer_by_kind
        and category_id in transfer_cat_ids
    ):
        direction = infer_transfer_kind(f"{category_name_raw} {description or ''}".strip())
        # HIGH#5 — si el texto no decide la dirección (muchos bancos: BIZUM,
        # ABONO, NÓMINA, TRASPASO… no llevan RECIBIDA/REALIZADA), caer al
        # SIGNO del extracto, que es prueba directa de la dirección.
        if direction is None and bank_sign != 0:
            direction = CategoryKind.INCOME if bank_sign > 0 else CategoryKind.EXPENSE
        if direction is not None:
            current_kind = (category_kinds or {}).get(category_id)
            if current_kind != direction:
                sibling = transfer_by_kind.get(direction)
                if sibling is not None:
                    category_id = sibling
                else:
                    # HIGH#4 — falta la categoría de transferencia del kind
                    # correcto. NO dejamos la dirección errónea en silencio
                    # (reintroduce el bug "BBVA a 0 con ingreso neto" de
                    # lessons.md): marcamos la fila para revisión.
                    direction_label = (
                        "recibida (ingreso)"
                        if direction == CategoryKind.INCOME
                        else "enviada (gasto)"
                    )
                    review_note = (
                        f"Transferencia {direction_label} pero no tienes una "
                        "categoría de transferencia de esa dirección. Revisa "
                        "antes de confirmar para no invertir el signo del saldo."
                    )
    # Dirección de categorías NORMALES desde el SIGNO del extracto
    # (AUDIT finding #1). Sólo cuando el banco declara el signo
    # (`bank_sign != 0`) y la categoría resuelta no es transferencia
    # (esas ya las maneja el bloque anterior por texto).
    elif (
        category_id is not None
        and bank_sign != 0
        and category_kinds is not None
        and category_id in category_kinds
    ):
        expected_kind = CategoryKind.INCOME if bank_sign > 0 else CategoryKind.EXPENSE
        current_kind = category_kinds[category_id]
        if current_kind != expected_kind:
            # El extracto contradice el kind de la categoría resuelta. La
            # verdad es el signo del banco. Buscamos una categoría hermana
            # del kind correcto (mismo nombre) para no persistir un signo
            # erróneo.
            sibling_name = resolved_name
            if sibling_name is None:
                # Categoría resuelta vía bank-mapping/regla/default: no
                # tenemos su nombre aquí, pero podemos intentar con el
                # concepto del banco si coincide en el lookup.
                sibling_name = category_name_raw.casefold().strip() or None
            sibling = (
                (sibling_by_name_kind or {}).get((sibling_name, expected_kind))
                if sibling_name
                else None
            )
            if sibling is not None:
                category_id = sibling
            else:
                # Sin hermana: dejamos la categoría resuelta pero marcamos
                # la fila para revisión en el preview. No perdemos la tx ni
                # silenciamos el conflicto.
                direction_label = "ingreso/abono" if bank_sign > 0 else "gasto/cargo"
                # `current_kind` es el de la categoría resuelta (el que
                # contradice al extracto).
                resolved_label = "ingreso" if current_kind == CategoryKind.INCOME else "gasto"
                review_note = (
                    "El extracto marca esta línea como "
                    f"{direction_label} pero la categoría asignada es de "
                    f"{resolved_label}. Revisa la categoría antes de confirmar."
                )

    # PHASE-34 (modelo de dinero + tarjeta): el `flow` lo manda el SIGNO del
    # extracto + la detección de movimiento interno (transferencia / pago de
    # tarjeta) por categoría o descripción. La compra "PAGO CON TARJETA" no
    # matchea los patrones internos → queda como gasto (OUT). Sin signo en el
    # extracto, la dirección cae al texto y luego al kind de la categoría
    # resuelta (extractos sólo-magnitud); sin ninguna señal queda sin
    # clasificar (None) — neutro, como una tx sin categoría.
    classify_text = f"{category_name_raw} {description or ''}".strip()
    category_is_transfer = bool(transfer_cat_ids and category_id in transfer_cat_ids)
    flow = classify_import_flow(
        bank_sign=bank_sign,
        text=classify_text,
        category_is_transfer=category_is_transfer,
        category_kind=(category_kinds or {}).get(category_id) if category_id else None,
    )

    import_hash = _compute_hash(
        user_id=user_id,
        amount=amount,
        currency=currency,
        occurred_at=occurred_at,
        description=description,
    )

    return (
        ParsedRow(
            amount=amount,
            occurred_at=occurred_at,
            description=description,
            category_id=category_id,
            import_hash=import_hash,
            flow=flow,
            statement_balance=_parse_balance(balance_raw),
            classify_text=classify_text,
            category_is_transfer=category_is_transfer,
        ),
        review_note,
    )


def _parse_amount_signed(value: str) -> tuple[Decimal, int]:
    """Acepta `1.234,56`, `1,234.56`, `25.50`, signos `+`/`-` y
    símbolos de moneda comunes (`€`, `$`, `£`, ` EUR`, ` USD`...).

    Devuelve `(magnitud_positiva, sign)` donde `sign` es:
      `-1` el extracto trae el importe en negativo (cargo / gasto),
      `+1` el extracto trae el importe en positivo con `+` explícito
           (abono / ingreso señalado de forma inequívoca),
       `0` el extracto NO declara dirección (importe sin signo): el
           caso de muchos CSV donde la dirección la da la categoría.

    El sistema almacena importes siempre positivos y deduce el signo
    de la categoría (income/expense). PERO el signo del extracto, cuando
    existe, es la VERDAD sobre la dirección del movimiento (lección
    PHASE-28/31/32: la dirección se deriva del extracto, no de
    `category.kind`). Por eso lo devolvemos como señal separada en lugar
    de descartarlo con `abs()` — un abono (+) que un bank-mapping mal
    aprendido clasifica como gasto restaría del saldo. El caller usa el
    signo para forzar/validar el kind de la categoría resuelta.

    Limpieza: filtra cualquier carácter que no sea dígito, separador
    decimal/miles (`.`, `,`) o signo (`+`, `-`). Eso elimina espacios,
    símbolos de moneda (€/$/£), códigos ISO al final ("3310,00 EUR")
    y cualquier otro adorno que el banco añada al PDF.
    """
    # AUDIT-2026-07 (LOW): un negativo puede venir entre paréntesis
    # "(1.234,56)" (formato contable) o con el signo AL FINAL "1.234,56-"
    # (algunos bancos españoles). `re.sub` elimina los paréntesis y el
    # `startswith("-")` no veía el signo final, así que ambos se colaban como
    # positivos → un cargo entraba con signo +. Los normalizamos a negativo.
    raw = value.strip()
    negative_paren = raw.startswith("(") and raw.endswith(")")
    cleaned = re.sub(r"[^\d.,+-]", "", value)
    sign = 0
    if negative_paren or cleaned.startswith("-") or cleaned.endswith("-"):
        sign = -1
    elif cleaned.startswith("+") or cleaned.endswith("+"):
        sign = 1
    # Quita cualquier signo (inicial o final) antes de parsear los dígitos.
    cleaned = cleaned.strip("+-")
    cleaned = _normalize_decimal_separators(cleaned)
    try:
        amount = Decimal(cleaned)
    except InvalidOperation as e:
        raise _RowError(f"importe inválido: {value!r}") from e
    amount = abs(amount)
    if amount <= 0:
        raise _RowError(f"importe debe ser distinto de cero: {value!r}")
    return amount.quantize(Decimal("0.01")), sign


def _normalize_decimal_separators(cleaned: str) -> str:
    """Normaliza separadores de miles/decimal a punto decimal.

    Compartida por `_parse_amount_signed` y `_parse_balance` (PHASE-39)
    para que importe y saldo interpreten `1.234,56` / `1,234.56` / `1.500`
    exactamente igual.
    """
    has_comma = "," in cleaned
    has_dot = "." in cleaned
    if has_comma and has_dot:
        # Asume el último es decimal
        if cleaned.rfind(",") > cleaned.rfind("."):
            return cleaned.replace(".", "").replace(",", ".")
        return cleaned.replace(",", "")
    if has_comma:
        return cleaned.replace(",", ".")
    if has_dot and cleaned.count(".") == 1:
        # AUDIT finding #4: desambiguar miles vs. decimal cuando sólo hay
        # un punto y ninguna coma. "1.500" europeo son MIL QUINIENTOS, no
        # uno coma cinco. Heurística por nº de dígitos tras el separador:
        #   - exactamente 3 dígitos y un único punto → separador de miles
        #     (`1.500` → 1500, `12.345` → 12345).
        #   - 1 ó 2 dígitos → decimal anglosajón (`25.50` → 25.5).
        #   - más de 3 dígitos (`1234.5678`) → decimal (no es agrupación
        #     de miles válida).
        # No afecta a los casos ya soportados arriba (coma decimal es-ES y
        # punto-miles + coma-decimal viajan por las ramas previas).
        decimals = cleaned.split(".", 1)[1]
        if len(decimals) == 3:
            return cleaned.replace(".", "")
    return cleaned


def _parse_balance(value: str | None) -> Decimal | None:
    """PHASE-39 — parsea la columna Saldo del extracto a Decimal FIRMADO.

    Diferencias deliberadas con `_parse_amount_signed`:
    - El saldo conserva su signo (puede ser negativo — descubierto — o 0);
      el importe se almacena como magnitud + señal de signo separada.
    - Es TOLERANTE: el saldo es informativo, así que un valor ilegible
      devuelve `None` en lugar de lanzar `_RowError` — nunca tumba la fila.
    """
    if not value or not value.strip():
        return None
    raw = value.strip()
    negative_paren = raw.startswith("(") and raw.endswith(")")
    cleaned = re.sub(r"[^\d.,+-]", "", raw)
    negative = negative_paren or cleaned.startswith("-") or cleaned.endswith("-")
    cleaned = cleaned.strip("+-")
    if not cleaned:
        return None
    cleaned = _normalize_decimal_separators(cleaned)
    try:
        balance = Decimal(cleaned)
    except InvalidOperation:
        return None
    if negative:
        balance = -balance
    return balance.quantize(Decimal("0.01"))


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
    occurrence: int = 0,
) -> str:
    """SHA-256 sobre los campos clave de una transacción.

    AUDIT finding #2: `occurrence` es el índice ordinal (0-based) de esta
    fila dentro de su grupo de filas idénticas en el MISMO lote
    (user+amount+currency+date+desc). Sin él, dos transacciones legítimas
    idénticas el mismo día (p. ej. dos cafés de 3,50 € sin componente
    horario en el extracto) colapsan al mismo hash y la segunda se
    descartaba en silencio.

    Con el ordinal:
      - Dos líneas distintas del MISMO fichero → ordinales 0, 1 → hashes
        distintos → ambas se importan.
      - Re-importar el MISMO fichero → las filas salen en el mismo orden,
        cada una recibe el mismo ordinal → mismos hashes → idempotente
        (las captura `find_existing_hashes`).

    `occurrence=0` (default) reproduce el hash histórico para grupos de
    una sola fila, así que los imports previos siguen siendo idempotentes.
    """
    parts = [
        str(user_id),
        f"{amount:.2f}",
        currency,
        occurred_at.isoformat(),
        (description or "").strip().casefold(),
    ]
    if occurrence:
        # Sólo se añade para la 2ª+ ocurrencia: preserva el hash histórico
        # del caso común (1 fila por grupo) y evita rehashear imports ya
        # persistidos.
        parts.append(f"#{occurrence}")
    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


async def _build_category_lookup(db: AsyncSession, user_id: uuid.UUID) -> dict[str, uuid.UUID]:
    """Mapa case-insensitive `name → id` de las categorías del usuario."""
    result = await db.execute(select(Category.id, Category.name).where(Category.user_id == user_id))
    return {name.casefold(): cat_id for cat_id, name in result.all()}


async def _build_category_kinds(
    db: AsyncSession, user_id: uuid.UUID
) -> tuple[dict[uuid.UUID, CategoryKind], dict[tuple[str, CategoryKind], uuid.UUID]]:
    """AUDIT finding #1 — Carga el kind de cada categoría del usuario.

    Devuelve dos mapas:
      - `kind_by_id`: `category_id → CategoryKind`. Permite al pipeline
        comparar el signo del extracto con el kind de la categoría
        resuelta y detectar contradicciones (un abono clasificado como
        gasto).
      - `sibling_by_name_kind`: `(name_casefold, kind) → category_id`.
        Permite reasignar a la "categoría hermana" del kind correcto
        cuando hay contradicción: una categoría con el MISMO nombre pero
        el kind que dicta el signo del banco (p. ej. "Transferencias"
        income vs. expense). Si no existe la hermana, el caller deja la
        resuelta y marca la fila para revisión.
    """
    rows = (
        await db.execute(
            select(Category.id, Category.name, Category.kind).where(Category.user_id == user_id)
        )
    ).all()
    kind_by_id: dict[uuid.UUID, CategoryKind] = {}
    sibling_by_name_kind: dict[tuple[str, CategoryKind], uuid.UUID] = {}
    for cat_id, name, kind in rows:
        kind_by_id[cat_id] = kind
        sibling_by_name_kind[(name.casefold().strip(), kind)] = cat_id
    return kind_by_id, sibling_by_name_kind


async def _user_owns_category(db: AsyncSession, user_id: uuid.UUID, category_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(Category.id).where(Category.id == category_id, Category.user_id == user_id)
    )
    return result.scalar_one_or_none() is not None
