# PHASE-23 — `CategoryKind.TRANSFER` + sospechosas no emparejadas

**Estado**: ✅ completada
**Rama**: `feat/phase-23-transfer-category`
**Fecha de merge**: 2026-05-15

## Objetivo

Cubrir el caso "una pata sola": cuando el usuario importa el extracto
de **una** de sus cuentas, las transferencias entre sus propias cuentas
aparecen como líneas "TRANSFERENCIA REALIZADA / RECIBIDA" sin
contraparte importada. El matcher de PHASE-21.3 sólo empareja cuando
existen las dos mitades en el sistema, así que estas líneas seguían
contando indebidamente como gasto/ingreso real.

Esta fase añade un tercer `CategoryKind` (`transfer`) que se excluye de
todos los agregados de cashflow igual que el `transfer_pair_id IS NOT
NULL`, y una UI específica para revisar y marcar las txs candidatas
("Sospechosas") en la pantalla de transferencias.

## Qué se implementó

### Backend — `CategoryKind.TRANSFER`

- `categories/models.py`: añadido `TRANSFER = "transfer"` al `StrEnum`
  con docstring explicando la semántica (mismo efecto que pareja
  detectada).
- **Migración `m0c14e6a9f7c3_categorykind_transfer.py`**:
  - `ALTER TYPE categorykind ADD VALUE 'TRANSFER'` dentro de
    `autocommit_block` (Postgres no permite usar el value recién
    añadido en la misma tx).
  - Seed: `UPDATE categories SET kind = 'TRANSFER' WHERE name ILIKE
    '%transfer%'` — cubre las categorías predeterminadas
    ("Transferencias", "Transferencia a favor") sin tocar nombres
    legítimos de income/expense.
  - Downgrade: revierte el seed a EXPENSE; el value `TRANSFER` queda
    huérfano en el enum (Postgres no soporta DROP VALUE).

### Backend — exclusión en agregados de cashflow

- `dashboard/repository.py`:
  - Nuevo helper `_exclude_transfer_kind(query, *, outer_join)` que
    aplica `Category.kind != TRANSFER` (o `is_(None) OR != TRANSFER`
    si hay outer join) — evita repetir el patrón.
  - Aplicado en `list_user_currencies`, `get_totals_by_kind`,
    `get_summary_aggregates` (incluido el `unconv_subq`),
    `get_breakdown_by_category` y `get_totals_by_month`.
  - `get_top_expenses` ya filtra `kind == EXPENSE`, así que excluye
    TRANSFER implícitamente.
- `budgets/repository.py::sum_expenses_in_period`: filtra `kind ==
  EXPENSE`, exclusión implícita.
- `transfers/repository.py::list_unmatched_active_transactions`:
  excluye txs ya marcadas como kind=TRANSFER del pool del matcher —
  están fuera del cashflow y no necesitan ser emparejadas (idempotente
  pero evita "sugerencias" redundantes).

### Backend — sospechosas + marcar

Nuevos endpoints en `transfers/router.py`:

- **`GET /transfers/suspects`** — devuelve `list[TransferSuspect]`:
  txs activas, sin pareja, no categorizadas kind=TRANSFER, cuya
  descripción matchea `ILIKE '%transfer%'`. Incluye categoría actual
  (si la tienen) para que la UI muestre el contexto antes de remarcar.
- **`POST /transfers/mark`** — body `{ transaction_id }`. Asigna la
  primera categoría kind=TRANSFER del usuario; si no existe, crea
  "Transferencia interna" con color/icon neutros y la asigna. La tx
  sale automáticamente del cashflow. 404 si la tx no es del usuario;
  409 si ya forma parte de un par.

Internamente:
- `repository.list_suspect_transactions` con LEFT JOIN a Category.
- `repository.get_or_create_default_transfer_category` — getter
  idempotente.
- `repository.assign_category` — setter simple.
- `service.list_suspects` y `service.mark_as_transfer` orquestan.

### Frontend — capa shared

- `@crisol/types`:
  - `CategoryKind`: `'income' | 'expense' | 'transfer'`.
  - Nuevos `TransferSuspect`, `TransferMarkRequest`, `TransferMarkResponse`.
- `@crisol/services`:
  - `transfersApi.suspects()`, `transfersApi.mark(payload)`.
  - `useTransferSuspects()` (query), `useMarkTransfer()` (mutation —
    invalida transfers + transactions + dashboard + budgets +
    accounts.balances + categories).
  - Nueva clave `queryKeys.transfers.suspects()`.
- `@crisol/ui`:
  - `formatCategoryKind(kind)` — etiqueta humana ("Ingreso" /
    "Gasto" / "Transferencia"). Aceptamos `string` para no acoplar
    `@crisol/ui` a `@crisol/types` (ADR 0001).

### Frontend — UI web

- `apps/web/app/(app)/settings/categories/page.tsx`:
  - Tercera opción "Transferencia" en el Select de tipo (crear + editar).
  - Nueva sección "Transferencias" en el listado, agrupada como las
    de gastos/ingresos.
  - `KindBadge` factorizado: usa `kindBadgeStyle` con `textMuted`
    para transfer (neutro).
- `apps/web/app/(app)/personal-finance/transfers/page.tsx`:
  - Nueva sección **"Sospechosas"** entre la cabecera y "Pares
    activos", visible sólo si hay suspects. Cada fila muestra
    importe + cuenta + fecha + descripción + categoría actual + botón
    "Marcar como transferencia". Inline `<SuspectCard>` (no se
    extrae a componente porque sólo se usa aquí).
- `apps/web/components/transactions/transaction-list.tsx`:
  `<TransferBadge>` ahora también se muestra cuando la categoría tiene
  `kind === 'transfer'`, no sólo cuando hay `transfer_pair_id`.
- Dropdowns que mostraban `(Gasto/Ingreso)` actualizados a
  `formatCategoryKind`: transactions/transaction-form, imports
  (upload + preview), receipts/confirm-form, settings/categories/rules.

### Frontend — UI mobile

- `apps/mobile/components/categories/category-form-modal.tsx`:
  Segmented control con tres opciones (Gasto / Ingreso / Transferencia).
- `apps/mobile/app/(modules)/personal-finance/categories.tsx`:
  Nueva sección "Transferencias" en el listado.
- `apps/mobile/app/(modules)/personal-finance/transfers.tsx`:
  Sección **"Sospechosas"** con `SuspectCard` inline (paridad con web).
- `apps/mobile/app/(modules)/personal-finance/(tabs)/transactions.tsx`:
  Badge "Transferencia" ahora se muestra también para txs con
  categoría kind=transfer (no sólo `transfer_pair_id`).

## Flujo técnico

```
Usuario importa extracto BBVA (CSV)
    │
    │ Las líneas "TRANSFERENCIA REALIZADA" entran como txs normales
    │ con categoría "Transferencias" (asignada por reglas o manualmente)
    │
    ▼
Migración m0c14e... reasignó "Transferencias" → kind=transfer
    │
    ▼
Dashboard / Presupuestos / Top expenses
    │ AND (category.kind IS NULL OR category.kind != 'transfer')
    ▼
→ Las txs marcadas como transferencia quedan FUERA del cashflow,
  pero SÍ impactan al saldo de la cuenta (accounts/repository.py no
  filtra kind=transfer en `get_balances_for_user`).

Caso "una pata sola sin categorizar":
    │ Usuario va a /personal-finance/transfers
    │ Sección "Sospechosas" lista las txs con "transfer" en descripción
    │ Click "Marcar como transferencia"
    ▼
POST /transfers/mark
    │ - get_or_create_default_transfer_category(user_id)
    │ - tx.category_id = transfer_cat.id
    ▼
Invalidación TanStack: transfers + transactions + dashboard + budgets
    │
    ▼
La tx desaparece de "Sospechosas", aparece como kind=transfer en el
listado de transacciones (badge "Transferencia"), no cuenta en
cashflow.
```

## Archivos clave

Backend:
- `backend/app/modules/personal_finance/categories/models.py` — enum
- `backend/app/modules/personal_finance/transfers/{schemas,repository,service,router}.py`
- `backend/app/modules/personal_finance/dashboard/repository.py` — helper + filtros
- `backend/alembic/versions/m0c14e6a9f7c3_categorykind_transfer.py`

Frontend shared:
- `packages/types/src/models/{category,transfer}.ts`
- `packages/types/src/dto/transfer.dto.ts`
- `packages/services/src/api/endpoints/transfers.ts`
- `packages/services/src/query/hooks/useTransfers.ts`
- `packages/services/src/query/keys.ts`
- `packages/ui/src/format.ts` — `formatCategoryKind`

Frontend web:
- `apps/web/app/(app)/personal-finance/transfers/page.tsx` — sospechosas
- `apps/web/app/(app)/settings/categories/page.tsx` — tercer kind

Frontend mobile:
- `apps/mobile/app/(modules)/personal-finance/transfers.tsx` — sospechosas
- `apps/mobile/app/(modules)/personal-finance/categories.tsx` — tercera sección
- `apps/mobile/components/categories/category-form-modal.tsx`

## Endpoints añadidos

- `GET /transfers/suspects` — txs candidatas a transferencia
- `POST /transfers/mark` — marca una tx asignando categoría kind=transfer

## Migraciones

- `m0c14e6a9f7c3_categorykind_transfer.py` — añade `TRANSFER` al enum +
  reasigna categorías con "transfer" en el nombre.

## Verificación

- [x] `pytest tests/test_transfers.py` — 17 tests verdes (incluye 6
      nuevos PHASE-23: suspects filter, mark create-default,
      mark reuse, mark 409 paired, mark excludes from dashboard,
      matcher skips kind=transfer).
- [x] `pytest` completo — 363/363 verde.
- [x] `pnpm typecheck` — 4/4 verde.
- [x] `pnpm lint` — 4/4 verde.
- [x] `pnpm test` — web 45/45, mobile 18/18.
- [x] Smoke manual: tras `alembic upgrade head`, el dashboard del
      usuario deja de mostrar las dos txs de 5000€ de BBVA en
      income/expense (las categorías "Transferencias" / "Transferencia
      a favor" pasaron a kind=transfer por el seed de la migración).

## Decisiones tomadas

- **Tres mecanismos coexisten** para excluir del cashflow:
  1. `transfer_pair_id IS NOT NULL` (PHASE-21.3, pareja detectada).
  2. `category.kind = 'transfer'` (PHASE-23, una pata o
     categorización explícita).
  3. El matcher heurístico ignora las (2) — no las propone como
     candidatas porque ya están excluidas.
- **El seed por nombre es agresivo intencionadamente**: cualquier
  categoría con "transfer" en el nombre pasa a kind=transfer. Si un
  usuario tenía "Transferencias del cliente" como ingreso real,
  perderá ese ingreso del cashflow hasta que cambie el kind de vuelta
  a `income` desde la UI. Trade-off aceptado: el caso de uso típico
  (transferencias internas) supera al edge case.
- **El detector de sospechosas usa `ILIKE '%transfer%'`** — no es
  configurable desde la UI (follow-up posible). Asume que los bancos
  españoles usan "TRANSFERENCIA" de forma consistente; otros idiomas
  matchean por "transfer".
- **`formatCategoryKind` acepta `string`, no `CategoryKind`** —
  evita acoplar `@crisol/ui` a `@crisol/types` (ADR 0001). La función
  cae al label "Gasto" para valores no reconocidos.
- **No se añade un campo `is_transfer` en `transactions`** — se
  modela vía categoría para reutilizar el rules engine (PHASE-20):
  cuando el usuario marca como transfer, el sistema puede aprender el
  patrón y auto-categorizar en futuros imports sin intervención.

## Limitaciones conocidas

- El patrón de detección `%transfer%` no es configurable desde la UI.
  Si el extracto del usuario usa "TRASPASO" o un código bancario sin
  la palabra "transfer", no aparece en sospechosas (el usuario puede
  asignar la categoría kind=transfer manualmente desde el formulario
  de la tx).
- No hay UX de "deshacer marca" en la sección Sospechosas — para
  revertir una tx mal marcada, el usuario edita la tx y le cambia
  la categoría a una de gasto/ingreso real.
- El seed agresivo (cualquier nombre con "transfer") puede dejar
  algunas categorías mal marcadas en casos edge — el usuario las
  revierte desde settings/categories.

## Próxima fase

PHASE-24 — Cross-currency transfers (pendiente desde PHASE-21.3).
