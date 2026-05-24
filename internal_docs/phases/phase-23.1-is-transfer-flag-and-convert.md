# PHASE-23.1 — `Category.is_transfer` flag + convertir a transferencia con destino

**Estado**: ✅ completada
**Rama**: `feat/phase-23-transfer-category` (continúa la rama de PHASE-23)
**Fecha de merge**: 2026-05-16

## Objetivo

Dos motivos para esta sub-fase:

1. **Bug de balance** introducido por PHASE-23. Usar `CategoryKind.TRANSFER`
   acopló dos responsabilidades distintas: el `kind` decide el **signo**
   con el que una tx afecta al saldo de su cuenta (asset+expense →
   `-amount`, asset+income → `+amount`); usarlo también como flag de
   "exclusión del cashflow" hizo que las txs con kind=TRANSFER cayeran
   al `else_=amount` del case statement, inflando saldos (el BBVA del
   usuario quedó +10.120€ por encima del real).

2. **Nueva feature**: convertir una tx existente en transferencia
   interna eligiendo cuenta destino — el sistema crea automáticamente
   la contraparte en la cuenta destino y empareja ambas vía
   `transfer_pair_id`. Ambas cuentas reflejan el movimiento real en
   sus saldos.

Ambas cosas en una fase porque la feature necesita el modelo correcto:
si conservas kind=TRANSFER no puedes asignar signos opuestos a origen
y destino, y la contraparte que crearías rompería el balance.

## Qué se implementó

### Backend — refactor `kind` ↔ `is_transfer`

- `categories/models.py`: `CategoryKind` vuelve a ser `INCOME |
  EXPENSE`. Nueva columna `Category.is_transfer: bool` (default
  False).
- **Migración `n1d25f7ba0e8d4_category_is_transfer_flag.py`**:
  - `ALTER TABLE categories ADD COLUMN is_transfer BOOLEAN DEFAULT FALSE`.
  - Restaura el kind original de las categorías que PHASE-23 había
    mutado a TRANSFER: inferencia por nombre (`%favor%`/`%recibida%`
    /`%entrada%` → INCOME, resto → EXPENSE) + `is_transfer=true`.
  - El value `TRANSFER` permanece huérfano en el enum (Postgres no
    soporta DROP VALUE) pero el código deja de usarlo.

### Backend — queries y lógica

- `dashboard/repository.py`: helper `_exclude_transfer_kind` ahora
  filtra `Category.is_transfer = false` (o IS NULL en outerjoin).
  Sustituye `kind != TRANSFER` en `_apply_scope` invocado desde
  `get_summary_aggregates`, `get_breakdown_by_category`,
  `get_totals_by_kind` y el `unconv_subq`. `get_totals_by_month` y
  `list_user_currencies` actualizados igual.
- `transfers/repository.py`:
  - `list_unmatched_active_transactions` y `list_suspect_transactions`
    excluyen txs con `is_transfer=true` (no necesitan emparejarse).
  - `get_or_create_default_transfer_category(db, user_id, *, kind)`
    devuelve la primera categoría `is_transfer=true` con el kind
    pedido; si no existe crea "Transferencia interna (salida)"
    (kind=EXPENSE) o "Transferencia interna (entrada)" (kind=INCOME)
    según el caso.
- `transfers/service.py`:
  - `mark_as_transfer` infiere el kind por descripción (`REALIZADA`/
    `RECIBIDA`/`a favor`/`entrante`) para preservar el signo del
    balance al asignar la categoría.
  - Nuevo `convert_to_internal_transfer(source_id, destination_acc_id)`:
    valida origen + destino (cuenta distinta + misma moneda; el
    cross-currency queda para una fase posterior), determina el kind
    de la contraparte (opuesto al del origen), crea la tx contraparte
    en `destination_account_id` con `source=MANUAL` + categoría
    `is_transfer=true` del kind correcto, y empareja vía
    `transfer_pair_id`.
- `transfers/router.py`: nuevo endpoint
  **`POST /transfers/from-source`** con body
  `{ source_transaction_id, destination_account_id }`.
- `categories/{schemas,service}.py`: schemas exponen `is_transfer`
  en create / update / response; el service lo propaga al constructor
  de `Category`.
- `seed/{dataset,service}.py`: la categoría "Transferencias" del seed
  ahora se crea con `is_transfer=true` desde el primer arranque del
  usuario (antes dependía de la migración de PHASE-23 para serlo, lo
  cual ya no aplica a usuarios nuevos).

### Frontend — capa shared

- `@crisol/types`:
  - `CategoryKind = 'income' | 'expense'` (revertido).
  - `Category` gana `is_transfer: boolean`.
  - `CategoryCreateRequest` / `CategoryUpdateRequest` aceptan
    `is_transfer?: boolean`.
  - Nuevo `TransferFromSourceRequest`.
- `@crisol/services`:
  - `transfersApi.fromSource(payload)`.
  - `useConvertToTransfer()` (mutation) — invalida transfers +
    transactions + dashboard + budgets + accounts.balances.
- `@crisol/ui`:
  - `formatCategoryKind` vuelve a ser binario ("Ingreso" / "Gasto").

### Frontend — UI web

- `settings/categories/page.tsx`:
  - El dropdown "Tipo" vuelve a `Gasto | Ingreso`.
  - Nuevo checkbox **"Es transferencia interna (excluir del cashflow)"**
    en formularios crear + editar.
  - Agrupamiento del listado: las `is_transfer=true` se separan en
    su propia sección "Transferencias" aunque internamente sean
    kind=expense / kind=income.
  - `KindBadge` muestra "Gasto · Transfer" / "Ingreso · Transfer"
    en color neutro cuando `is_transfer`.
- `transactions/transaction-list.tsx`: badge "Transferencia" cubre
  ahora tanto `transfer_pair_id !== null` como `category?.is_transfer`.
- **Nuevo `components/transfers/convert-to-transfer-dialog.tsx`**:
  Card en el detalle de la transacción que sólo aparece cuando la tx
  no está emparejada. Lista cuentas del usuario activas con la misma
  moneda (excluye la cuenta origen) en un dropdown, botón "Convertir
  en transferencia" → `useConvertToTransfer` → toast + redirige a
  `/personal-finance/transfers`.
- `personal-finance/transactions/[id]/page.tsx`: integra el nuevo
  dialog tras el form de edición.

### Frontend — UI mobile

- `components/categories/category-form-modal.tsx`:
  - Segmented control vuelve a Gasto / Ingreso.
  - Nuevo checkbox "Es transferencia interna" debajo de los
    appearance fields, alimenta `is_transfer` en el submit.
- `app/(modules)/personal-finance/categories.tsx`: el grupo
  "Transferencias" filtra por `is_transfer` (no por kind).
- `app/(modules)/personal-finance/(tabs)/transactions.tsx`: badge
  "Transferencia" igual que en web.
- **Nuevo `components/transfers/convert-to-transfer-block.tsx`**:
  Block compacto con chips de cuentas elegibles + CTA. Reutiliza
  `useConvertToTransfer`.
- `app/(modules)/personal-finance/transaction/[id].tsx`: monta
  `ConvertToTransferBlock` debajo del formulario cuando la tx no está
  emparejada.

### Tests backend

`tests/test_transfers.py` reescribe las assertions de PHASE-23 al
nuevo modelo + añade tests específicos:

- `mark` crea/reutiliza categoría is_transfer del kind correcto.
- `mark` infiere kind=INCOME desde "RECIBIDA".
- `mark` preserva signo del balance (asset+expense → -amount tras
  marcar, no +amount como antes del refactor).
- `from-source` crea contraparte, empareja, balances cambian
  correctamente (-amount en origen, +amount en destino), cashflow
  agregado queda en 0.
- `from-source` rechaza misma cuenta (400) y cross-currency (400).
- Matcher heurístico salta categorías `is_transfer=true`.

20/20 tests del módulo + 366/366 suite completa verde.

### Tests frontend

Fixtures de `Category` actualizadas en 7 tests (4 web + 3 mobile)
para incluir `is_transfer: false`.

## Flujo "Convertir en transferencia"

```
Usuario abre el detalle de una tx en BBVA (ej. -500€ "Traspaso a broker")
    │
    ▼
Card "¿Es un movimiento entre tus cuentas?"
    │ Dropdown con cuentas elegibles (misma moneda, no la origen, no archivadas)
    │ Selecciona "Broker"
    │ Click "Convertir en transferencia"
    ▼
POST /transfers/from-source
    │ Validaciones: origen activo + sin pareja, destino distinto +
    │ misma moneda
    │
    │ Infiere kind contraparte = INCOME (porque origen es EXPENSE)
    │ get_or_create_default_transfer_category(kind=INCOME)
    │   → "Transferencia interna (entrada)" si no existe
    │
    │ Crea tx en Broker:
    │   amount=500, currency=EUR, occurred_at=mismo
    │   category=Transferencia interna (entrada)  [is_transfer=true, INCOME]
    │   description="Transferencia desde BBVA"
    │   source=MANUAL
    │
    │ link_pair(source, counterpart) → bidireccional
    │
    ▼
Saldos: BBVA -500 (asset+expense), Broker +500 (asset+income)
Cashflow agregado: ambas excluidas (transfer_pair_id IS NOT NULL)
Toast + redirige a /personal-finance/transfers
```

## Archivos clave

Backend:
- `backend/app/modules/personal_finance/categories/models.py`
- `backend/app/modules/personal_finance/categories/schemas.py`
- `backend/app/modules/personal_finance/categories/service.py`
- `backend/app/modules/personal_finance/dashboard/repository.py`
- `backend/app/modules/personal_finance/transfers/{repository,service,router,schemas}.py`
- `backend/app/modules/personal_finance/seed/{dataset,service}.py`
- `backend/alembic/versions/n1d25f7ba0e8d4_category_is_transfer_flag.py`

Frontend shared:
- `packages/types/src/models/{category,transfer}.ts`
- `packages/types/src/dto/{category,transfer}.dto.ts`
- `packages/services/src/api/endpoints/transfers.ts`
- `packages/services/src/query/hooks/useTransfers.ts`
- `packages/ui/src/format.ts`

Frontend web:
- `apps/web/app/(app)/personal-finance/transactions/[id]/page.tsx`
- `apps/web/components/transfers/convert-to-transfer-dialog.tsx`
- `apps/web/app/(app)/settings/categories/page.tsx`

Frontend mobile:
- `apps/mobile/app/(modules)/personal-finance/transaction/[id].tsx`
- `apps/mobile/components/transfers/convert-to-transfer-block.tsx`
- `apps/mobile/components/categories/category-form-modal.tsx`

## Endpoints añadidos

- `POST /transfers/from-source` — convierte tx + crea contraparte en
  destino + empareja.

## Migraciones

- `n1d25f7ba0e8d4_category_is_transfer_flag.py` — añade
  `categories.is_transfer` + restaura kind original de categorías
  kind=TRANSFER + marca con `is_transfer=true`.

## Verificación

- [x] `pytest tests/test_transfers.py` — 20/20 verde
      (incluye 7 nuevos PHASE-23.1).
- [x] `pytest` completo — 366/366 verde.
- [x] `pnpm typecheck` — 4/4 verde.
- [x] `pnpm lint` — 4/4 verde.
- [x] `pnpm test` — web 45/45, mobile 18/18.
- [x] Smoke manual: query directa a la BD confirma que las tres txs
      de transferencia del usuario contribuyen correctamente al saldo
      BBVA: -5000 + 5000 - 60 = **-60€** neto (era +10.060€ con el
      bug de PHASE-23).

## Decisiones tomadas

- **`is_transfer` en `categories`, no en `transactions`**: la "es
  transferencia" suele ser propiedad estable de una categoría
  ("Bizum enviado entre mis cuentas", "Transferencias propias"), no
  algo que cambias por transacción. Además permite que el rules
  engine de PHASE-20 herede la marca automáticamente al asignar la
  categoría.
- **El value `TRANSFER` queda huérfano en el enum** porque Postgres
  no soporta DROP VALUE. Inofensivo: ningún código lo emite y los
  datos ya están migrados.
- **Inferencia heurística por descripción** en `mark` y por kind
  origen en `from-source` (vs pedir al usuario): el caso común es
  TRANSFERENCIA REALIZADA → outflow; el usuario puede editar la
  categoría si discrepa, sin añadir fricción al flujo principal.
- **`from-source` rechaza cross-currency** (400) en lugar de hacer
  conversión silenciosa: el usuario debe ser consciente del tipo de
  cambio aplicado. La implementación queda en backlog.
- **No preservamos la categoría original del origen** al hacer
  `convert_to_internal_transfer`: el origen mantiene su categoría
  actual (puede ser "Bizum enviado" con `is_transfer=false`); lo
  que excluye del cashflow es el `transfer_pair_id` que se pone tras
  emparejar, no la categoría. Así el usuario conserva el grain
  semántico ("fue un bizum") sin perder la separación contable.

## Limitaciones conocidas

- Cross-currency transfers no soportados (origen y destino deben
  tener la misma moneda) — rechazo explícito en `from-source`.
- No hay UX de "deshacer conversión" más allá del flujo genérico de
  unlink en `/personal-finance/transfers`.
- La heurística de inferencia de kind por descripción asume español
  (`REALIZADA`/`RECIBIDA`). Otros idiomas pueden defaultear a
  EXPENSE; el usuario corrige editando la categoría.

## Próxima fase

PHASE-24 — Cross-currency transfers (origen y destino en distintas
monedas, conversión vía rates del día).
