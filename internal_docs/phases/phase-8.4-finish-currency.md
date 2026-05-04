# PHASE-8.4 — Cierre fase 8: transactions cross-currency + polish

**Estado**: ✅ completada
**Rama**: `feat/phase-8.4-finish-currency`
**PR**: —
**Fecha de merge**: 2026-05-04

## Objetivo

Cerrar el último cabo grande de la fase 8 (multimoneda): la tabla de
transacciones todavía hacía conversión per-row en cliente con
`useQueries` por fecha distinta, mientras el resto del dashboard ya
recibía importes convertidos del backend desde PHASE-8.3. Esta fase
unifica el patrón: el backend convierte cada fila al recibir
`?target_currency=` y la tabla pinta el `≈ €X` directamente desde la
respuesta, sin fetches adicionales.

Además consolida tres mejoras que quedaban en backlog tras 8.3:

- `top-expenses` distingue **convertido vs original** vía dos campos
  nuevos (`original_amount`, `original_currency`).
- `unconvertible_count` deja de ser una segunda query — pasa a
  **subquery escalar** dentro del SELECT del summary.

## Qué se implementó

### Backend — `/transactions` con `?target_currency=`

`backend/app/modules/personal_finance/transactions/`:

- `repository.list_transactions` acepta `target_currency: str | None`.
  Cuando viene, el SELECT añade un segundo campo `converted_amount`
  computado con `converted_amount_expr` (helper SQL ya existente de
  PHASE-8.3 — la misma subquery correlacionada que usa `dashboard`).
  Sin target, el campo es `NULL`.
- `service.list_transactions` dispara `ensure_rates_for_user_scope`
  antes del listado cuando hay target — backfill on-demand de tasas
  para fechas con transacciones (mismo helper que dashboard, ahora
  público y reutilizable).
- `router.list_endpoint` expone `target_currency` como query param
  con validación 3-letras y construye la respuesta enriqueciendo
  cada fila con `converted_amount` + `converted_currency` cuando
  procede.
- `schemas.TransactionResponse` añade `converted_amount` y
  `converted_currency` opcionales (default `None` en lecturas
  individuales y modo legacy).

`dashboard/service.ensure_rates_for_user_scope` se renombra desde
`_ensure_rates_in_scope` (era helper privado) — ahora `transactions`
también lo invoca. Los 4 callsites en `dashboard.service` se
actualizaron.

### Backend — `top-expenses` expone `original_amount` + `original_currency`

`dashboard/schemas.TopExpenseItem` añade los dos campos. El service
los rellena siempre desde el `Transaction` (nunca son `None`):

- En modo cross-currency (`target_currency`): `amount` es el
  convertido — el ranking se hace por convertido —, `original_*`
  trae el dato crudo de la fila.
- En modo legacy: `amount` y `original_*` coinciden (ambos son el
  valor original de la transacción).

El frontend gana así la capacidad de pintar "$120 USD (~100 €)" sin
consultar la transacción individual.

### Backend — `unconvertible_count` como subquery escalar

`dashboard/repository`:

- Nuevo `get_summary_aggregates` reemplaza las 3 queries serial que
  hacía `service.get_summary` (`get_totals_by_kind` +
  `count_transactions` + `count_unconvertible`). Una sola consulta
  con:
  - `SUM(CASE WHEN kind='income' THEN amount END)` →
    income total.
  - `SUM(CASE WHEN kind='expense' THEN amount END)` →
    expense total.
  - `COUNT(Transaction.id)` (sobre `OUTER JOIN Category`) →
    `transaction_count` (incluye txs sin categoría).
  - **Scalar subquery** `SELECT COUNT(*) FROM transactions WHERE
    NOT amount_is_convertible_expr(target)` → `unconvertible_count`.
    En modo legacy es literal `0` y la subquery no se ejecuta.
- Las funciones legacy `count_transactions` y `count_unconvertible`
  se eliminan (no quedaban callers fuera del service).

`service.get_summary` pasa de 3 awaits a 1 (más el opcional de
previous-period). Una round-trip menos por request al endpoint que
suele encabezar la cascada del dashboard.

### Frontend — tipos y página de transacciones

- `packages/types/src/models/transaction.ts`: `Transaction` añade
  `converted_amount: string | null` y `converted_currency: string | null`.
- `packages/types/src/dto/transaction.dto.ts`: `TransactionListQuery`
  añade `target_currency?: string`.
- `packages/types/src/models/dashboard.ts`: `TopExpenseItem` añade
  `original_amount: string` y `original_currency: string`.
- `apps/web/app/(app)/personal-finance/transactions/page.tsx`: lee
  `convertAll` del store y, cuando está ON, pasa
  `target_currency: currency` al hook `useTransactions`. Sin toggle,
  comportamiento legacy intacto.

### Frontend — tabla simplificada (drop `useQueries` por fecha)

`apps/web/components/transactions/transaction-list.tsx` se reescribe:

- Se eliminan las dependencias `useQueries`, `exchangeRatesQueryOptions`,
  `formatConverted`, `RatesMap` y el cómputo de `uniqueDates`/
  `ratesByDate`/`useMemo` previo.
- La columna `Importe` consume `tx.converted_amount` +
  `tx.converted_currency` directamente cuando la moneda original
  difiere de la activa y `convertAll` está ON.
- `≈ —` cuando el backend devolvió `null` (sin tasa para esa
  fecha) — mismo signal UX que en PHASE-8.2 pero sin hacer un fetch
  fallido.
- El tooltip se compone con el dato crudo de la fila (no necesita ya
  el rates map cliente):
  `"USD 100,00 convertido a EUR con la tasa del 2026-02-19"`.

Coste pre-PHASE-8.4: 5–15 fetches por página de 20 filas en frío.
Coste tras PHASE-8.4: **0 fetches adicionales** — la conversión va
incluida en la respuesta del listado.

## Flujo técnico

```
 Página transacciones
    │ filters + (convertAll ? target_currency: activeCurrency)
    ▼
 GET /transactions?target_currency=USD&...
    │
    ▼
 service.list_transactions
    ├── ensure_rates_for_user_scope  ─▶ backfill on-demand
    │     (mismo helper que dashboard)
    └── repository.list_transactions(target_currency=USD)
            └── SELECT t.*, converted_amount_expr('USD') AS converted
                  FROM transactions t
                  WHERE t.user_id=?  AND ... [filters]
                  ORDER BY occurred_at DESC LIMIT/OFFSET
    ▼
 router._build_response: rellena converted_amount/converted_currency
    ▼
 Frontend transaction-list.tsx pinta tx.converted_amount sin fetches
```

## Archivos clave

- `backend/app/modules/personal_finance/transactions/repository.py`
- `backend/app/modules/personal_finance/transactions/service.py`
- `backend/app/modules/personal_finance/transactions/router.py`
- `backend/app/modules/personal_finance/transactions/schemas.py`
- `backend/app/modules/personal_finance/dashboard/repository.py`
  (nuevo `get_summary_aggregates`, eliminadas
  `count_transactions`/`count_unconvertible`)
- `backend/app/modules/personal_finance/dashboard/service.py`
  (`get_summary` simplificado;
  `ensure_rates_for_user_scope` público)
- `backend/app/modules/personal_finance/dashboard/schemas.py`
  (TopExpenseItem + original_amount/original_currency)
- `backend/tests/test_dashboard_cross_currency.py` (6 tests nuevos)
- `packages/types/src/models/transaction.ts`
- `packages/types/src/dto/transaction.dto.ts`
- `packages/types/src/models/dashboard.ts`
- `apps/web/app/(app)/personal-finance/transactions/page.tsx`
- `apps/web/components/transactions/transaction-list.tsx`

## Endpoints modificados

| Método | Ruta | Cambio |
|--------|------|--------|
| GET | `/transactions` | Acepta `target_currency` (3 letras). Cada fila gana `converted_amount: Decimal\|null` y `converted_currency: string\|null`. |
| GET | `/dashboard/top-expenses` | Cada item gana `original_amount: Decimal` y `original_currency: string`. |
| GET | `/dashboard/summary` | Implementación interna pasa de 3 queries a 1; respuesta idéntica. |

## Migraciones

Ninguna.

## Verificación

- [x] `pnpm lint` verde.
- [x] `pnpm typecheck` verde.
- [x] `pnpm test` — 39 tests pasan (8 web + 31 services + 0 cambios
      en tests viejos).
- [x] `pytest backend/tests/` — 164/164 (6 nuevos en
      `test_dashboard_cross_currency.py`).
- [x] `mypy app/` — 13 errores pre-existentes en
      `ai/client.py` (Pillow stubs) y `dashboard/conversion.py`
      (SQLAlchemy `InstrumentedAttribute` typing); **0 introducidos
      por esta fase**.
- [ ] Smoke manual con datos reales del usuario — pendiente.

## Decisiones tomadas

- **`converted_amount` viaja como nuevo campo de la fila, no como
  envelope del listado**. Mantener la respuesta plana significa que
  el frontend no necesita saber si fue cross-currency para indexar
  los items. El campo es `null` cuando no procede; aceptable.
- **Backend no quantiza el converted_amount** — devuelve full
  precision `Decimal` (igual que el dashboard). El frontend redondea
  con `formatAmount` según la moneda destino. Coherente con el
  resto del módulo.
- **`ensure_rates_for_user_scope` se promueve de privado a público
  cross-módulo** en lugar de duplicar el helper. CLAUDE.md permite
  imports cross-submódulo dentro de `personal_finance/` por ser
  parte del mismo dominio. La alternativa (mover a `currency.service`)
  rompe encapsulación porque el helper conoce `Transaction`.
- **`get_summary_aggregates` reemplaza 3 queries por 1**. La
  limitación pre-existente decía "hacerlo subquery en el mismo
  SELECT es trivial" — se cumple. La subquery escalar de
  `unconvertible_count` sólo se evalúa cuando hay
  `target_currency`; en modo legacy es literal `0`.
- **`get_totals_by_kind` se mantiene** porque sigue siendo el camino
  para el cálculo de `previous_period_*` (no necesita
  `unconvertible_count`).
- **Smart Recent Activity en dashboard no se convierte**. La sidebar
  "Actividad reciente" del dashboard sigue mostrando importes en
  moneda original. No es un bug: es una vista compacta de 4 items
  donde la conversión añadiría ruido. Si se decide que debe
  alinearse con el toggle, follow-up.
- **Eliminar `useQueries` por fecha vale el cambio de contrato del
  backend**. La alternativa "mantener cliente" se justificó en 8.2
  cuando `/transactions` no tenía conversión; con el endpoint nuevo,
  mantener el patrón cliente es duplicación. La línea de menos
  resistencia era trasladar al backend.

## Limitaciones conocidas

- **Recent activity sin convertir** (decidido). Follow-up trivial si
  se quiere alinear: exponer `target_currency` también en la query
  con `limit=4` y consumir `tx.converted_amount` en el componente
  `StitchRecentActivity`.
- **`get_summary_aggregates` consolida 3 → 1 query, pero el cálculo
  de `previous_period_*` sigue añadiendo otra**. Si pasamos de 4
  awaits a 2 awaits es bueno; consolidar al 100% requeriría una
  sola query gigante con doble scope, no compensa la complejidad.
- **JPY redondeo a 2 decimales** sigue pendiente — sin datos reales
  JPY en el sistema todavía.
- **Cron nocturno de tasas** — no implementado, lazy fetch sigue
  cubriendo el caso "primer uso del día".

## Próxima fase

Sin definir. Candidatos del backlog (sin priorizar):

- `StitchRecentActivity` con `target_currency` (cierre completo).
- Cron nocturno (APScheduler) para refresh proactivo de tasas.
- Política `quantize` per-currency cuando entren datos JPY.
- Detección de subscripciones recurrentes vía AI.
- Modelo de presupuestos por categoría con alertas.
- Drawer mobile para la sidebar.
