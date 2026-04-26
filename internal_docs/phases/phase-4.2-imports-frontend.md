# PHASE-4.2 — Imports frontend

**Estado**: ✅ completada
**Rama**: `feat/phase-4.2-imports-frontend`
**PR**: —
**Fecha de merge**: 2026-04-26

## Objetivo

Interfaz web para subir extractos bancarios CSV/XLSX, mapear las
columnas del fichero a los campos del dominio y ver el resumen del
job creado en PHASE-4.1.

## Qué se implementó

- **Tipos en `@finanzas/types`**:
  - `ImportJob`, `ImportJobStatus`, `ImportColumnMappings`,
    `ImportErrorEntry` (modelos).
  - `ImportListQuery`, `ImportListResponse` (DTO).
- **API client en `@finanzas/services`**:
  - `importsApi.list/get/create`. `create` envía `multipart/form-data`
    con `file`, `column_mappings` (JSON), `currency` y
    `default_category_id` opcional.
  - `queryKeys.imports.{all, list, detail}` con normalización de
    filtros como el resto.
  - Hooks `useImports`, `useImport`, `useCreateImport`. La mutación
    invalida `imports`, `transactions` y `dashboard` para que las
    transacciones recién importadas se reflejen en otras pantallas.
- **Wizard web (`apps/web/app/(dashboard)/imports/`)**:
  - `page.tsx` — listado paginado de jobs previos con badge de estado
    y contadores rápidos.
  - `new/page.tsx` — wizard de 3 pasos con stepper visual:
    1. Upload (file + currency + default category).
    2. Mapping (4 campos con detección de cabeceras CSV).
    3. Result (estadísticas + errores + acciones).
  - `[id]/page.tsx` — detalle de un job, reutiliza `ResultStep`.
- **Componentes (`apps/web/components/imports/`)**:
  - `upload-step.tsx`, `mapping-step.tsx`, `result-step.tsx`,
    `import-list.tsx`, `status-badge.tsx`.
  - `detect-csv-headers.ts` — heurística cliente que prueba `,`, `;` y
    `\t` y elige el delimitador con más columnas. Soporta cabeceras
    entrecomilladas con coma interna. Solo se aplica a `.csv`/`.tsv`;
    para XLSX el usuario teclea el nombre de columna manualmente.
- **Nav**: link "Importar" en `(dashboard)/layout.tsx`.
- **Tests**:
  - `imports.test.ts` — 4 tests del API client (FormData con/sin
    `default_category_id`, paths correctos).
  - `keys.test.ts` — 3 tests añadidos para `queryKeys.imports`.
  - `detect-csv-headers.test.ts` — 5 tests del detector (coma, punto y
    coma, comillas con coma interna, no-CSV, una sola columna).

## Flujo técnico

```
   /imports                     /imports/new
   ┌──────────────┐             ┌──────────────┐
   │ ImportsPage  │             │ NewImportPage│
   │ (lista)      │             │ (wizard)     │
   └──────┬───────┘             └──────┬───────┘
          │ useImports                 │
          ▼                            ▼ step state
   ┌──────────────┐         ┌─────────┬─────────┬─────────┐
   │ /imports     │         │ Upload  │ Mapping │ Result  │
   └──────────────┘         └────┬────┴────┬────┴─────────┘
                                 │         │
                                 ▼         │
                            detectCsv      │
                            Headers        │
                                           ▼
                                    useCreateImport
                                           │ POST /imports (multipart)
                                           ▼
                                    invalidate(imports,
                                               transactions,
                                               dashboard)
```

## Archivos clave

- `packages/types/src/models/import.ts` — modelos del dominio.
- `packages/types/src/dto/import.dto.ts` — DTO de listado.
- `packages/services/src/api/endpoints/imports.ts` — cliente API.
- `packages/services/src/query/hooks/useImports.ts` — hooks TanStack
  Query (incluye invalidación cruzada).
- `packages/services/src/query/keys.ts` — añade `imports.*`.
- `apps/web/app/(dashboard)/imports/page.tsx` — listado.
- `apps/web/app/(dashboard)/imports/new/page.tsx` — wizard contenedor
  con state machine `upload → mapping → result`.
- `apps/web/app/(dashboard)/imports/[id]/page.tsx` — detalle de job.
- `apps/web/components/imports/{upload,mapping,result}-step.tsx`,
  `import-list.tsx`, `status-badge.tsx`, `detect-csv-headers.ts`.
- `apps/web/app/(dashboard)/layout.tsx` — link de navegación.

## Endpoints consumidos

(Sin cambios en backend.)

| Método | Ruta | Uso |
|--------|------|-----|
| POST | `/imports` | `useCreateImport` desde el wizard (paso 2). |
| GET  | `/imports` | `useImports` en `/imports`. |
| GET  | `/imports/{id}` | `useImport` en `/imports/[id]`. |

## Decisiones tomadas

- **Solo web**. Móvil queda fuera (el dev-spec lo marca opcional). El
  flujo natural es desktop con un fichero descargado del banco.
- **Wizard cliente, sin endpoint de preview**. El backend de 4.1
  procesa síncronamente; añadir un `?dry_run` cambiaría el contrato.
  Si en el futuro se nota fricción, será un cambio pequeño y aditivo.
- **Detección de cabeceras solo para CSV**. Parsear XLSX en el browser
  requeriría una librería extra (`xlsx`/`exceljs`). Para XLSX el
  usuario teclea el nombre de columna; el backend valida igual.
- **`FileReader` en lugar de `Blob.text()`**. jsdom (entorno de tests)
  no implementa `Blob.text()` ni `Blob.slice().text()`. Ver lessons.
- **Estado del wizard en `useState` local**. Es un flujo lineal de 3
  pasos en una sola página; meterlo en Zustand sería sobreingeniería.

## Verificación

- [x] `pnpm lint` verde (4 paquetes).
- [x] `pnpm typecheck` verde (4 paquetes).
- [x] `pnpm test` verde (43 tests: 12 ui + 23 services + 8 web).
- [ ] Smoke manual con CSV real — pendiente del usuario al levantar
  el stack (`docker compose up -d` + `pnpm dev:web` + login + subir
  CSV bancario).

## Limitaciones conocidas

- No hay edición de jobs ni reintento desde la UI (el backend no lo
  soporta tampoco — se re-sube el fichero).
- El mapeo es texto libre: si el usuario teclea un nombre de columna
  que no existe en el fichero, el job termina con `rows_failed`.
- En XLSX no se sugieren cabeceras al usuario (limitación del
  detector cliente — requeriría una dependencia adicional).
- Sin progress bar — el pipeline backend es síncrono y el spinner
  cubre la espera.

## Próxima fase

PHASE-5.1 — Receipts backend (IA local: Ollama + qwen2.5-vl, módulo
`receipts/`, pipeline de extracción de tickets).
