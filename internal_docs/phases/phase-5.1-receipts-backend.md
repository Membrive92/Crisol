# PHASE-5.1 — Receipts backend

**Estado**: ✅ completada
**Rama**: `feat/phase-5.1-receipts-backend`
**PR**: —
**Fecha de merge**: 2026-04-26

## Objetivo

Pipeline de tickets fotográficos: el usuario sube una imagen, el modelo
de visión local (Ollama + qwen2.5-vl) extrae los datos estructurados,
el usuario los confirma o rechaza y al confirmar se crea una
`Transaction` con `source=receipt`.

## Qué se implementó

- **Infra**:
  - `docker-compose.yml` añade el servicio `minio` (puertos 9000/9001,
    volumen `miniodata`).
  - `pyproject.toml` añade `minio>=7.2.0` y `httpx>=0.27.0` (runtime).
- **`backend/app/core/storage.py`**: cliente MinIO singleton con
  `put_receipt`, `get_receipt`, `delete_receipt`. Crea bucket on
  demand y guarda los blobs como `<user_id>/<YYYYMMDD>/<uuid>.<ext>`.
  Único punto del backend que conoce las credenciales de MinIO.
- **`backend/app/modules/ai/`**:
  - `client.generate_with_image(prompt, image, model?, json_mode=True)`
    — POST `/api/generate` a Ollama con la imagen en base64 y formato
    JSON. Mismas excepciones que el resto del cliente
    (`AiUnavailableError`, `AiTimeoutError`).
  - `service.extract_receipt(image)` — orquesta prompt + parse + valida
    con `ReceiptExtraction`. Lanza `AiInvalidOutputError` si la
    respuesta no es JSON o no encaja con el schema.
  - `schemas` añade `ReceiptExtraction` y `ReceiptLineItem`.
- **`backend/app/modules/receipts/`** (nuevo):
  - `models.Receipt` con `ReceiptStatus` (`pending|confirmed|rejected`),
    `blob_key`, `content_type`, `extraction` (JSON), `transaction_id`
    nullable.
  - `repository`: `create_receipt`, `get_receipt_by_id`, `list_receipts`.
  - `service`: `extract_and_persist`, `confirm_receipt`,
    `reject_receipt`. Lista blanca de mime-types
    (`image/jpeg|png|webp|heic|heif`). Si la IA falla, borra el blob
    para no dejar huérfanos (HTTP 502).
  - `router`: 5 endpoints (`POST /receipts/extract`,
    `POST /receipts/{id}/confirm`, `POST /receipts/{id}/reject`,
    `GET /receipts`, `GET /receipts/{id}`).
- **Migración** `a91d8f4c2e10_receipts_module.py` crea la tabla
  `receipts` con índices por `user_id` y `transaction_id`. **No** se
  añade FK `transactions.receipt_id → receipts.id` para evitar el
  ciclo bidireccional con `receipts.transaction_id`; la integridad
  inversa basta y `service.confirm_receipt` mantiene la consistencia.
- **`app/main.py`** registra `receipts_router`.
- **Config**: `Settings` añade `minio_endpoint`, `minio_access_key`,
  `minio_secret_key`, `minio_bucket_receipts`, `minio_secure`.
- **Tests**:
  - `test_ai_service.py` (3) — mock de `client.generate_with_image`:
    extracción válida, JSON inválido, schema inválido.
  - `test_receipts.py` (9) — flujo HTTP con `storage` y `ai_service`
    mockeados: extract feliz, mime no soportado, payload vacío, IA
    caída (limpia blob), confirm crea transacción, doble confirm 409,
    reject sin transacción, list & get, aislamiento multi-usuario.

## Flujo técnico

```
   POST /receipts/extract  (multipart: file=imagen)
        │
        ▼
   service.extract_and_persist
   ├─ valida content_type ∈ image/{jpeg,png,webp,heic,heif}
   ├─ storage.put_receipt → blob_key
   ├─ ai_service.extract_receipt(payload)
   │     ├─ ai.client.generate_with_image (Ollama, json mode)
   │     └─ json.loads + ReceiptExtraction.model_validate
   │     └─ on error: storage.delete_receipt + 502
   └─ create_receipt(status=pending, extraction=dump)
        │
        ▼
   201 { receipt, extraction }

   POST /receipts/{id}/confirm  body: { amount, occurred_at, currency, ... }
        │
        ▼
   service.confirm_receipt
   ├─ status debe ser pending → 409 si no
   ├─ valida category_id (si lo hay) pertenece al usuario
   ├─ crea Transaction(source=receipt, receipt_id=...)
   └─ marca receipt.status=confirmed + receipt.transaction_id

   POST /receipts/{id}/reject  → status=rejected (no crea transacción)
```

## Endpoints añadidos

| Método | Ruta | Auth | Body / Query | Response |
|--------|------|------|--------------|----------|
| POST   | `/receipts/extract` | sí | multipart `file` (imagen ≤8 MB) | `201` `{ receipt, extraction }` |
| POST   | `/receipts/{id}/confirm` | sí | `{ amount, occurred_at, currency, description?, category_id? }` | `200` `ReceiptResponse` |
| POST   | `/receipts/{id}/reject` | sí | — | `200` `ReceiptResponse` |
| GET    | `/receipts` | sí | `limit`, `offset` | `200` `{ items, total, limit, offset }` |
| GET    | `/receipts/{id}` | sí | — | `200` `ReceiptResponse` |

## Archivos clave

- `backend/app/core/storage.py` — wrapper MinIO.
- `backend/app/modules/ai/{client,service,schemas}.py` — cliente
  vision + extracción.
- `backend/app/modules/receipts/{models,schemas,repository,service,router}.py`.
- `backend/alembic/versions/a91d8f4c2e10_receipts_module.py`.
- `backend/app/main.py` — registra router.
- `backend/app/core/config.py` — vars MinIO.
- `backend/pyproject.toml` — `minio`, `httpx`.
- `docker-compose.yml` — servicio `minio`.
- `backend/tests/test_ai_service.py` y `tests/test_receipts.py`.

## Decisiones tomadas

- **Sin FK desde `transactions.receipt_id`**. Hay un ciclo lógico
  (Receipt ↔ Transaction); en el modelo se mantiene un único FK formal
  (`receipts.transaction_id → transactions.id`). La consistencia
  inversa la garantiza `service.confirm_receipt`.
- **Extracción síncrona dentro del request**. Tiempo dominado por
  Ollama (segundos a decenas), aceptable. Si en el futuro se vuelve
  un problema se mueve a tarea de fondo sin cambiar el contrato (el
  receipt ya tiene estado `pending`).
- **Mock del modelo en tests**. Probar contra Ollama real es lento y
  flaky; los tests cubren la integración HTTP, validación y flujo, y
  el smoke manual valida el modelo.
- **Bucket creado on-demand**. `storage._ensure_bucket` lo crea la
  primera vez que se usa, evita scripts de bootstrap.
- **Whitelist de mime-types**. Aceptamos JPEG/PNG/WebP/HEIC/HEIF;
  GIF/SVG/PDF/etc se rechazan con 400 (los PDFs van por `imports`).
- **Confirmación como POST y no PATCH**. Es una transición de estado
  más una creación de recurso secundario (transacción), no un update
  arbitrario del receipt.

## Verificación

- [x] `pytest tests/` — 81/81 (12 nuevos).
- [x] `ruff check app/` verde.
- [x] `mypy app/` verde (57 archivos).
- [x] `pnpm lint` + `typecheck` verdes (frontend no toca esta fase pero
  se verifica que sigue OK).
- [ ] Smoke manual con un ticket real subido por la futura UI 5.2.
- [ ] Smoke manual con `/receipts/extract` por curl (requiere Ollama
  con `qwen2.5-vl:7b` descargado y MinIO arriba).

## Limitaciones conocidas

- El modelo es no determinista. Tickets borrosos, en idiomas distintos
  o con tipografía rara pueden devolver datos incompletos o
  incorrectos. El usuario edita siempre antes de confirmar — la IA
  sugiere, no decide.
- `ReceiptExtraction.line_items` se persiste pero no se usa para crear
  transacciones individuales (el MVP crea **una** transacción con el
  total). Las líneas quedan en el JSON para consulta y para una
  posible iteración futura.
- Sin descarga del blob desde el API (no hay `GET /receipts/{id}/blob`).
  Si la UI lo necesita en 5.2, se añade un endpoint con presigned URL.
- Tamaño máximo 8 MB por imagen — fotos típicas de móvil entran sin
  problemas.
- No hay rate limiting; un usuario podría saturar Ollama. Aceptable
  en MVP single-tenant local.

## Próxima fase

PHASE-5.2 — Receipts frontend (cámara mobile + upload web, pantalla de
confirmación editable, integración con `useReceipts`).
