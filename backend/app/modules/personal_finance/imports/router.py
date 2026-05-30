"""Router del módulo imports."""

from __future__ import annotations

import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.ai import service as ai_service
from app.modules.ai.exceptions import AiError
from app.modules.personal_finance.bank_mappings.repository import (
    get_mappings_for_concepts,
    normalize_concept,
)
from app.modules.personal_finance.category_rules.repository import (
    find_first_matching_rule,
    list_rules_for_user,
)
from app.modules.personal_finance.imports.models import ImportJobStatus
from app.modules.personal_finance.imports.repository import get_job_by_id, list_jobs
from app.modules.personal_finance.imports.schemas import (
    ImportColumnMappings,
    ImportCommitRequest,
    ImportJobListResponse,
    ImportJobResponse,
    ImportPreviewBankConceptGroup,
    ImportPreviewResponse,
    ImportPreviewRow,
    ImportSource,
)
from app.modules.personal_finance.imports.service import (
    run_commit,
    run_import,
    run_preview,
)

router = APIRouter(prefix="/imports", tags=["imports"])

# 10 MB. Suficiente para extractos bancarios típicos.
MAX_UPLOAD_SIZE = 10 * 1024 * 1024


def _parse_account_id(raw: str | None) -> uuid.UUID:
    """Valida que `account_id` sea un UUID y lo devuelve.

    Lo lanzamos como 400 (validación de form) en lugar de 422 (Pydantic)
    para mantener un mensaje claro sin tener que envolver toda la
    metadata de form/file en un schema.
    """
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="account_id es obligatorio",
        )
    try:
        return uuid.UUID(raw)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="account_id no es un UUID válido",
        ) from e


@router.post("", response_model=ImportJobResponse, status_code=201)
async def create_import_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    file: Annotated[UploadFile, File(...)],
    column_mappings: Annotated[str, Form(..., description="JSON con el mapping de columnas")],
    account_id: Annotated[str, Form(..., description="UUID de la cuenta destino")],
    currency: Annotated[str, Form(min_length=3, max_length=3)] = "EUR",
    default_category_id: Annotated[str | None, Form()] = None,
) -> ImportJobResponse:
    """Sube un fichero CSV/XLSX, lo procesa síncronamente y devuelve el job."""
    parsed_account_id = _parse_account_id(account_id)
    try:
        mapping_data = json.loads(column_mappings)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"column_mappings no es JSON válido: {e}",
        ) from e

    try:
        mappings = ImportColumnMappings.model_validate(mapping_data)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=e.errors(),
        ) from e

    parsed_default_category: uuid.UUID | None = None
    if default_category_id:
        try:
            parsed_default_category = uuid.UUID(default_category_id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="default_category_id no es un UUID válido",
            ) from e

    payload = await file.read()
    if len(payload) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Fichero demasiado grande (máx {MAX_UPLOAD_SIZE} bytes)",
        )
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El fichero está vacío",
        )

    job = await run_import(
        db,
        user.id,
        account_id=parsed_account_id,
        filename=file.filename or "upload.csv",
        content_type=file.content_type,
        payload=payload,
        mappings=mappings,
        currency=currency,
        default_category_id=parsed_default_category,
    )
    await db.commit()
    return ImportJobResponse.model_validate(job)


@router.get("", response_model=ImportJobListResponse)
async def list_imports_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ImportJobListResponse:
    """Lista los jobs del usuario."""
    items, total = await list_jobs(db, user.id, limit=limit, offset=offset)
    return ImportJobListResponse(
        items=[ImportJobResponse.model_validate(j) for j in items],
        total=total,
        limit=limit,
        offset=offset,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Preview / commit (PHASE-18+): wizard en dos pasos.
#
# IMPORTANTE: estas rutas estáticas (`/preview`, `/{id}/commit`) deben ir
# ANTES de `GET /{job_id}` — si se declaran después, FastAPI matchea el path
# `/preview` como un job_id en la ruta del GET, ve que el método no coincide
# y devuelve 405 Method Not Allowed.
# ─────────────────────────────────────────────────────────────────────────────


# Cuántas filas devolvemos en el preview. El frontend muestra todas y deja
# al usuario hacer scroll; el resto del job tiene `total_rows` para que se
# entienda cuántas se importarían al confirmar.
PREVIEW_ROWS_LIMIT = 200


@router.post("/preview", response_model=ImportPreviewResponse, status_code=200)
async def preview_import_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    file: Annotated[UploadFile, File(...)],
    column_mappings: Annotated[str, Form(..., description="JSON con el mapping de columnas")],
    account_id: Annotated[str, Form(..., description="UUID de la cuenta destino")],
    currency: Annotated[str, Form(min_length=3, max_length=3)] = "EUR",
    default_category_id: Annotated[str | None, Form()] = None,
    force_vision: Annotated[bool, Form()] = False,
) -> ImportPreviewResponse:
    """Sube un fichero, lo parsea y devuelve las filas detectadas
    sin persistir transacciones. El job queda en estado PREVIEW
    para confirmar después con POST /imports/{id}/commit.

    `force_vision=true` salta pdfplumber y procesa el PDF con IA local.
    """
    parsed_account_id = _parse_account_id(account_id)
    try:
        mapping_data = json.loads(column_mappings)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"column_mappings no es JSON válido: {e}",
        ) from e

    try:
        mappings = ImportColumnMappings.model_validate(mapping_data)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=e.errors(),
        ) from e

    parsed_default_category: uuid.UUID | None = None
    if default_category_id:
        try:
            parsed_default_category = uuid.UUID(default_category_id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="default_category_id no es un UUID válido",
            ) from e

    payload = await file.read()
    if len(payload) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Fichero demasiado grande (máx {MAX_UPLOAD_SIZE} bytes)",
        )
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El fichero está vacío",
        )

    job = await run_preview(
        db,
        user.id,
        account_id=parsed_account_id,
        filename=file.filename or "upload.csv",
        content_type=file.content_type,
        payload=payload,
        mappings=mappings,
        currency=currency,
        default_category_id=parsed_default_category,
        force_vision=force_vision,
    )
    await db.commit()

    if job.status == ImportJobStatus.FAILED:
        first_error = job.error_log[0] if job.error_log else {"error": "Fallo desconocido"}
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(first_error.get("error", "Fallo desconocido")),
        )

    payload_data = job.preview_payload or {}
    raw_rows = payload_data.get("rows") or []
    source_value = payload_data.get("source") or ImportSource.CSV.value
    effective_mappings_data = payload_data.get("effective_mappings") or {}
    effective_mappings = ImportColumnMappings.model_validate(effective_mappings_data)

    preview_rows: list[ImportPreviewRow] = []
    for raw in raw_rows[:PREVIEW_ROWS_LIMIT]:
        preview_rows.append(
            ImportPreviewRow(
                amount=str(raw.get(effective_mappings.amount, "")),
                occurred_at=str(raw.get(effective_mappings.occurred_at, "")),
                description=(
                    str(raw.get(effective_mappings.description) or "")
                    if effective_mappings.description
                    else None
                )
                or None,
                category_name=(
                    str(raw.get(effective_mappings.category_name) or "")
                    if effective_mappings.category_name
                    else None
                )
                or None,
            )
        )

    # PHASE-19+20: agrupar filas por concepto del banco
    # (`category_name`) y resolver sugerencia de categoría en este orden:
    #   1. Equivalencia exacta guardada (`bank_category_mappings`).
    #   2. Reglas del usuario aplicadas a las filas reales del grupo:
    #      - Si TODAS las filas resuelven a la misma categoría → esa.
    #      - Si difieren → `has_mixed_rule_matches=True`, sin sugerencia
    #        (las reglas se aplican fila a fila en el commit).
    #   3. Sin sugerencia: el usuario asignará a mano (o IA si la pide).
    groups: list[ImportPreviewBankConceptGroup] = []
    if effective_mappings.category_name:
        # Recopila por concepto: filas concretas (concept, description) +
        # display + count. Usado luego para evaluar reglas con la
        # description real, no solo el concepto.
        order: list[str] = []
        display_by_norm: dict[str, str] = {}
        rows_by_norm: dict[str, list[tuple[str, str | None]]] = {}
        for raw in raw_rows:
            cell = str(raw.get(effective_mappings.category_name) or "").strip()
            if not cell:
                continue
            norm = normalize_concept(cell)
            if norm not in rows_by_norm:
                order.append(norm)
                display_by_norm[norm] = cell
                rows_by_norm[norm] = []
            description = (
                str(raw.get(effective_mappings.description) or "").strip()
                if effective_mappings.description
                else ""
            ) or None
            rows_by_norm[norm].append((cell, description))

        if order:
            saved_mappings = await get_mappings_for_concepts(db, user.id, order)
            rules = await list_rules_for_user(db, user.id, enabled_only=True)
            for norm in order:
                rows_in_group = rows_by_norm[norm]
                count = len(rows_in_group)

                suggested: uuid.UUID | None = None
                source: str | None = None
                mixed = False

                if (saved := saved_mappings.get(norm)) is not None:
                    suggested = saved
                    source = "saved_mapping"
                elif rules:
                    # Aplica reglas a cada fila del grupo. Si todas
                    # resuelven a la misma categoría, esa es la sugerencia.
                    resolved: set[uuid.UUID | None] = set()
                    for concept, description in rows_in_group:
                        rule = find_first_matching_rule(
                            rules, concept=concept, description=description
                        )
                        resolved.add(rule.category_id if rule else None)

                    non_null = {x for x in resolved if x is not None}
                    if len(non_null) == 1 and len(resolved) == 1:
                        # Todas las filas: misma categoría.
                        suggested = next(iter(non_null))
                        source = "rule"
                    elif len(non_null) >= 2:
                        # Filas con categorías diferentes → mixto.
                        mixed = True
                    # Si solo hay None resuelto, sin sugerencia.

                groups.append(
                    ImportPreviewBankConceptGroup(
                        concept=display_by_norm[norm],
                        count=count,
                        suggested_category_id=suggested,
                        suggestion_source=source,
                        has_mixed_rule_matches=mixed,
                    )
                )

    return ImportPreviewResponse(
        job_id=job.id,
        source=ImportSource(source_value),
        total_rows=len(raw_rows),
        rows=preview_rows,
        bank_concept_groups=groups,
    )


@router.post("/{job_id}/commit", response_model=ImportJobResponse)
async def commit_import_endpoint(
    job_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    body: ImportCommitRequest | None = None,
) -> ImportJobResponse:
    """Confirma un job en estado PREVIEW: persiste sus filas como
    transacciones y devuelve el job ya en COMPLETED.

    `body.category_overrides` mapea concepto del banco → category_id
    para asignar categorías a las filas y guardar la equivalencia para
    futuras importaciones. Si `body` es `None` no se aplican overrides.
    """
    overrides = body.category_overrides if body is not None else {}
    job = await run_commit(db, user.id, job_id=job_id, category_overrides=overrides)
    await db.commit()
    return ImportJobResponse.model_validate(job)


# ─────────────────────────────────────────────────────────────────────────────
# AI suggest (PHASE-20): para conceptos sin sugerencia (regla ni equivalencia
# guardada), pedir al modelo de texto local categorías razonables.
# ─────────────────────────────────────────────────────────────────────────────


class AiSuggestionResponse(BaseModel):
    """`suggestions[concept] = category_id | null` para los conceptos
    enviados al modelo. Conceptos sin entrada en la respuesta del
    modelo simplemente no aparecen."""

    suggestions: dict[str, uuid.UUID | None]


@router.post(
    "/{job_id}/ai-suggest",
    response_model=AiSuggestionResponse,
    status_code=200,
)
async def ai_suggest_endpoint(
    job_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AiSuggestionResponse:
    """Para un job en PREVIEW, pide al modelo de texto local que
    sugiera categorías para los conceptos del banco que aún no tienen
    sugerencia (sin equivalencia guardada y sin regla matching).

    Útil cuando las reglas seed/custom no cubren conceptos del usuario.
    No persiste nada — el frontend muestra las sugerencias para que el
    usuario confirme o corrija; al hacer commit se guardan las
    aceptadas como `bank_category_mappings`.
    """
    from app.modules.personal_finance.imports.models import ImportJobStatus
    from app.modules.personal_finance.imports.repository import get_job_by_id as _get_job

    job = await _get_job(db, job_id, user.id)
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
        return AiSuggestionResponse(suggestions={})

    # Detecta los conceptos únicos sin sugerencia previa: ni mapping
    # exacto ni regla matching para todas las filas del grupo.
    saved_mappings = await get_mappings_for_concepts(
        db,
        user.id,
        [str(r.get(effective_mappings.category_name) or "") for r in rows_raw],
    )
    rules = await list_rules_for_user(db, user.id, enabled_only=True)

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
        return AiSuggestionResponse(suggestions={})

    # Cargar categorías del usuario para el prompt.
    from app.modules.personal_finance.categories.models import Category

    cats_q = await db.execute(
        select(Category).where(Category.user_id == user.id).order_by(Category.name)
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

    # Mapeamos `id` (norm concept) → category_id (str). El frontend
    # espera el concepto en formato display, pero el normalizado es
    # estable. Lo devolvemos normalizado y el frontend hace el lookup
    # contra `bank_concept_groups[].concept` (también normalizable).
    suggestions: dict[str, uuid.UUID | None] = {}
    for concept_norm, cat_id_str in ai_result.items():
        if cat_id_str is None:
            suggestions[concept_norm] = None
            continue
        try:
            suggestions[concept_norm] = uuid.UUID(cat_id_str)
        except ValueError:
            suggestions[concept_norm] = None
    return AiSuggestionResponse(suggestions=suggestions)


# ─────────────────────────────────────────────────────────────────────────────
# Detalle por id — al final para que las rutas estáticas tengan prioridad.
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/{job_id}", response_model=ImportJobResponse)
async def get_import_endpoint(
    job_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ImportJobResponse:
    """Detalle de un job."""
    job = await get_job_by_id(db, job_id, user.id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job no encontrado")
    return ImportJobResponse.model_validate(job)
