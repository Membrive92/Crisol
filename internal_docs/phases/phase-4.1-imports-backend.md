# PHASE-4.1 — Imports backend

**Estado**: ✅ completada
**Rama**: `feat/phase-4.1-imports-backend`
**PR**: — (push directo a `main`)
**Fecha de merge**: 2026-04-24

## Objetivo

Importar transacciones desde ficheros CSV/XLSX bancarios con mapeo de
columnas configurable, deduplicación por hash, y persistencia del job
para auditoría.

## Qué se implementó

- **Módulo `backend/app/modules/imports/`**:
  - `models.py` — `ImportJob` + enum `ImportJobStatus`
    (`pending|processing|completed|failed`).
  - `schemas.py` — `ImportColumnMappings` (request), `ImportJobResponse`,
    `ImportJobListResponse`, `ImportErrorEntry`.
  - `parser.py` — parsers CSV (stdlib `csv` con sniffer de delimitador)
    y XLSX (`openpyxl`, `read_only=True`). Devuelve `list[dict[str, str]]`.
  - `repository.py` — `create_job`, `get_job_by_id`, `list_jobs`,
    `find_existing_hashes` (lookup por `Transaction.import_hash`).
  - `service.py` — `run_import` orquesta el pipeline completo.
  - `router.py` — 3 endpoints.
- **Pipeline síncrono** (suficiente para MVP):
  1. Crear job en estado `processing`.
  2. Parsear el fichero. Si falla → job `failed` con error_log.
  3. Por cada fila: mapping → validación → hash SHA-256.
  4. Dedup intra-batch (mismo hash dentro del CSV) e inter-batch
     (hashes ya en BD).
  5. Persistir transacciones con `source=import` + `import_hash`.
  6. Marcar job como `completed`.
- **`Transaction.import_hash`** (CHAR(64) NULLABLE) + índice único
  parcial `(user_id, import_hash) WHERE import_hash IS NOT NULL`.
- **Migración** `7c3a91f4d2b8_imports_module.py` crea `import_jobs`,
  añade la columna `import_hash` y el índice único parcial.
- **Tests**: 11 del flujo HTTP + 10 del parser. Cubren CSV con
  distintos delimitadores, XLSX, validación de filas, deduplicación
  intra/inter-batch, asignación de categoría por nombre, formato
  europeo de importes (`1.234,56`), aislamiento multi-usuario y
  fichero de formato no soportado (job termina en `failed`).
- **Fix preexistente**: FastAPI 0.116 introdujo un assert que rechaza
  endpoints con `status_code=204` y retorno tipado distinto de
  `Response`. Adaptados `auth/logout`, `categories/delete`,
  `transactions/delete` para usar `response_class=Response` y
  retornar `Response(status_code=204)` explícitamente. Ver lessons.

## Endpoints añadidos

| Método | Ruta | Body / Query | Response |
|--------|------|--------------|----------|
| POST | `/imports` | multipart: `file`, `column_mappings` (JSON), `currency` (def `EUR`), `default_category_id?` | `ImportJobResponse` (job ya finalizado) |
| GET  | `/imports` | `limit` (1..200, def 50), `offset` (def 0) | `ImportJobListResponse` |
| GET  | `/imports/{id}` | — | `ImportJobResponse` |

## Reglas de negocio

- **Mapping obligatorio mínimo**: `amount` y `occurred_at`. `description`
  y `category_name` opcionales.
- **Asignación de categoría por nombre**: lookup case-insensitive en
  las categorías del usuario. Si no hay match, queda con
  `default_category_id` (o `null`). No se crean categorías nuevas.
- **`default_category_id`** debe pertenecer al usuario, si no → 400.
- **Hash de dedup**: SHA-256 de
  `user_id|amount(2dp)|currency|occurred_at_iso|description.casefold().strip()`.
- **Importe**: positivo, soporta `1.234,56` (EU) y `1,234.56` (US).
- **Fecha**: ISO 8601 + formatos comunes europeos (`DD/MM/YYYY`,
  `DD-MM-YYYY`, `DD.MM.YYYY`).
- **Errores**: `error_log` cap a 100 entradas. `rows_failed` cuenta
  todas las filas inválidas, no solo las primeras 100.
- **Tamaño máx fichero**: 10 MB. Más → 413.
- **Fichero vacío** → 400.
- **Mapping JSON inválido** → 400. **Mapping sin `amount`/`occurred_at`** → 422.

## Archivos clave

- `backend/app/modules/imports/{models,schemas,parser,repository,service,router}.py`
- `backend/app/modules/transactions/models.py` — añade `import_hash` + índice.
- `backend/alembic/versions/7c3a91f4d2b8_imports_module.py` — migración.
- `backend/app/main.py` — registra `imports_router`.
- `backend/app/modules/{auth,categories,transactions}/router.py` —
  ajuste 204 (compat FastAPI 0.116+).
- `backend/tests/test_imports.py` — 11 tests del flujo.
- `backend/tests/test_imports_parser.py` — 10 tests del parser.

## Decisiones tomadas

- **Sync vs async**: pipeline síncrono dentro del request. Para MVP es
  suficiente; ficheros bancarios típicos < 10 MB se procesan en
  segundos. Si el escalado lo pide, se mueve a tarea de fondo sin
  cambiar la API (el job ya tiene estados).
- **Storage del fichero**: in-memory. No se guarda el original en
  MinIO. Si en el futuro hace falta auditoría completa se añadirá un
  campo `blob_key` y se subirá igual que con `receipts/`.
- **`import_hash` en `transactions`**: alternativa descartada — tabla
  separada `transaction_hashes`. La denormalización aquí es claramente
  mejor: el dedup es por usuario+hash, queda en una sola query, y
  borrar la transacción borra el hash automáticamente.
- **Índice único parcial**: solo aplica cuando `import_hash IS NOT NULL`
  (las transacciones manuales no tienen hash). PostgreSQL lo soporta
  nativamente con `WHERE`. Evita colisiones espurias entre el bucket
  de "sin hash".
- **Categoría por nombre case-insensitive**: practical — los CSV
  bancarios suelen venir en mayúsculas o minúsculas inconsistentes.
- **`response_class=Response` en 204**: ver lesson L-001.

## Verificación

- [x] `pytest tests/` — 61/61 verde (21 nuevos).
- [x] `ruff check app/` verde.
- [x] `mypy app/` verde (49 archivos).
- [x] Aislamiento multi-usuario probado (job_a no es visible para user_b).
- [x] Frontend typecheck sigue verde tras los cambios en endpoints 204.

## Limitaciones conocidas

- Sin almacenamiento del fichero original. Si el usuario detecta un
  error, no puede re-procesar el mismo fichero — debe re-subirlo.
- Hash basado en `description.casefold().strip()` — dos transacciones
  con descripciones que solo difieren en puntuación se considerarían
  distintas. Aceptable para el MVP.
- Sin endpoint de "preview" antes de persistir. El job se ejecuta
  completo en una sola request. Cuando aparezca PHASE-4.2 (frontend)
  se evaluará si añadir `?dry_run=true`.
- Sin progress tracking durante el procesamiento (al ser síncrono
  no aplica todavía).

## Próxima fase

PHASE-4.2 — Imports frontend (wizard de subida, preview de mapeo,
resumen de resultados; web prioritario, mobile opcional).
