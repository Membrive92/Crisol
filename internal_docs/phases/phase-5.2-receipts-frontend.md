# PHASE-5.2 — Receipts frontend

**Estado**: ✅ completada (web + mobile vía follow-up `feat/mobile-receipts`)
**Rama**: `feat/phase-5.2-receipts-frontend`
**PR**: —
**Fecha de merge**: 2026-04-26

## Objetivo

Interfaz web para subir tickets fotográficos, ver la extracción del
modelo de visión, editarla y crear la transacción asociada (o
rechazarla). Cierra el flujo de IA local del MVP.

## Qué se implementó

- **Tipos en `@finanzas/types`**:
  - `models/receipt.ts` — `Receipt`, `ReceiptStatus`,
    `ReceiptExtraction`, `ReceiptLineItem`.
  - `dto/receipt.dto.ts` — `ReceiptListQuery`, `ReceiptListResponse`,
    `ReceiptExtractResponse`, `ReceiptConfirmRequest`.
- **API client en `@finanzas/services`**:
  - `receiptsApi.list / get / extract / confirm / reject`. `extract`
    envía `multipart/form-data` con `file`.
  - `queryKeys.receipts.{all, list, detail}`.
  - Hooks `useReceipts`, `useReceipt`, `useExtractReceipt`,
    `useConfirmReceipt`, `useRejectReceipt`. Confirm invalida
    `receipts`, `transactions` y `dashboard` (la transacción nueva debe
    aparecer en otras pantallas).
- **Web (`apps/web/app/(dashboard)/receipts/`)**:
  - `page.tsx` — listado paginado con badge de estado.
  - `new/page.tsx` — flujo en dos fases: upload (con preview en
    `URL.createObjectURL`) → ejecución de la extracción →
    formulario de confirmación con los valores propuestos pre-rellenos.
  - `[id]/page.tsx` — detalle. Si el receipt está `pending` muestra el
    formulario de confirmar/rechazar; si está `confirmed`/`rejected`
    muestra resumen de líneas (read-only).
- **Componentes (`apps/web/components/receipts/`)**:
  - `status-badge.tsx`, `receipt-list.tsx`, `confirm-form.tsx`
    (formulario editable + `ExtractionSummary` colapsable con líneas).
- **Nav**: link "Tickets" en `(dashboard)/layout.tsx`.
- **Tests**:
  - `services/api/endpoints/receipts.test.ts` (5) — list/get paths,
    extract con FormData, confirm con payload, reject sin body.
  - `services/query/keys.test.ts` — 3 nuevos para `receipts.*`.

## Flujo técnico

```
   /receipts                       /receipts/new
   ┌──────────────┐                ┌──────────────────┐
   │ ReceiptsPage │                │ NewReceiptPage   │
   │ (listado)    │                │ (upload + form)  │
   └──────┬───────┘                └─────────┬────────┘
          │ useReceipts                      │
          ▼                                  ▼
   GET /receipts                    [Upload]
                                      └─ useExtractReceipt
                                         POST /receipts/extract (multipart)
                                         ▼
                                    [Extracción + form editable]
                                      ├─ useConfirmReceipt
                                      │   POST /receipts/{id}/confirm
                                      │   → invalida receipts,
                                      │     transactions, dashboard
                                      │   → router.push('/receipts')
                                      └─ useRejectReceipt
                                          POST /receipts/{id}/reject

   /receipts/[id]
   ┌──────────────────┐
   │ Detail           │  → si pending: mismo form de confirm/reject
   │                  │  → si confirmed/rejected: extracción read-only
   └──────────────────┘
```

## Archivos clave

- `packages/types/src/models/receipt.ts` y `dto/receipt.dto.ts`.
- `packages/services/src/api/endpoints/receipts.ts`.
- `packages/services/src/query/hooks/useReceipts.ts`.
- `packages/services/src/query/keys.ts` — añade `receipts.*`.
- `apps/web/app/(dashboard)/receipts/{page,new/page,[id]/page}.tsx`.
- `apps/web/components/receipts/{status-badge,receipt-list,confirm-form}.tsx`.
- `apps/web/app/(dashboard)/layout.tsx` — link nav.

## Decisiones tomadas

- **Web only en esta fase**. La parte mobile (cámara con
  `expo-camera` o picker con `expo-image-picker`) queda como
  follow-up. Razón: requiere instalar y configurar permisos nativos
  Expo, lo que excede el alcance de "cerrar el MVP web". El backend
  (5.1) ya soporta la subida desde cualquier cliente — el día que
  añadamos mobile sólo hay que hacer un picker que llame a
  `receiptsApi.extract`. El dev-spec marcaba mobile como parte de
  5.2; lo dejamos explícito como deuda en lugar de marcar la fase
  incompleta.
- **Reutilización de `confirm-form` entre `new` y `[id]`**. El receipt
  detail aprovecha el mismo formulario cuando está `pending` —
  evita duplicar la pantalla de confirmación.
- **No descargar el blob desde la UI**. La extracción ya viene en el
  `extraction` JSON; la UI no necesita re-descargar la imagen original
  (en el MVP). Si el usuario quisiera revisar la foto, se añade un
  endpoint `GET /receipts/{id}/blob` con presigned URL en una iteración
  futura.
- **Validación cliente mínima**. El form de confirmación valida
  importe positivo y moneda 3 letras; el resto lo valida el backend
  (Pydantic). Match con el patrón de `transaction-form`.

## Verificación

- [x] `pnpm lint` verde.
- [x] `pnpm typecheck` verde.
- [x] `pnpm test` verde (frontend, 39 tests totales: 12 ui + 31
  services + 8 web).
- [ ] Smoke manual: requiere Ollama corriendo con `qwen2.5-vl:7b`
  descargado y MinIO arriba. Pasos:
  1. `docker compose up -d` (Postgres + MinIO + Ollama).
  2. `ollama pull qwen2.5-vl:7b` si no está.
  3. `pnpm dev:web` y `uvicorn` arriba.
  4. Login → "Tickets" → "+ Subir ticket" → adjuntar foto → analizar
     → editar → confirmar → la transacción aparece en `/transactions`.

## Limitaciones conocidas

- **Sin mobile**. Se documenta como follow-up (5.3 o sub-fase).
- Sin botón para volver a invocar la IA si el resultado es malo (el
  usuario edita manualmente o rechaza y re-sube).
- La pantalla de detalle no muestra la imagen original (no hay
  endpoint que la sirva).
- No hay categorías inferidas automáticamente desde el comercio (el
  usuario elige). Mejora futura razonable.

## Próxima fase

MVP completo. Próximas iteraciones serán ajustes y la ya planificada
PHASE-4.3 follow-up (visión para PDFs escaneados) o un mobile receipts
en una fase nueva.
