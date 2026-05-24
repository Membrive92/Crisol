# PHASE-24.1 — Cuotas de deuda persistidas + editables + estado de pago

**Estado**: ✅ completada
**Rama**: `feat/phase-24-debt-from-source` (continúa la rama de PHASE-24)
**Fecha de merge**: 2026-05-17

## Objetivo

Hasta PHASE-24, el cuadro de amortización era **calculado en vivo** a
partir de `apr + term_months + start_date + opening_balance`. El
usuario podía verlo pero no tocar nada — útil para previsualización,
inútil para reflejar la realidad:

- BBVA suele cobrar importes ligeramente distintos al cuadro francés
  teórico (redondeos, comisiones).
- No había forma de marcar qué cuotas ya estaban pagadas.
- El histórico real divergía del plan teórico sin reconciliación.

PHASE-24.1 **persiste las cuotas** en una tabla dedicada y permite:
1. Editar importe / fecha de cada cuota individual (override puntual).
2. Marcar / desmarcar cuotas como pagadas (con tx opcional vinculada).

Decisión arquitectónica: **los overrides NO recomputan las cuotas
siguientes**. El cuadro mantiene la estructura francesa inicial salvo
donde el usuario ajustó. Esto evita propagar cambios en cascada y
respeta lo que realmente cobra el banco.

## Qué se implementó

### Backend

- **Nueva tabla `liability_installments`**
  (`accounts/installments_model.py`):
  - `account_id`, `installment_index` (1..n, UNIQUE).
  - `due_date`, `payment`, `interest`, `principal`, `remaining_balance`.
  - `paid_at` (TZ-aware, nullable), `paid_transaction_id` (FK opcional
    a transactions).
- **Migración `n1d25f7ba0e8d4` → `o2e36g8cb1f9d5`**:
  - Crea la tabla con índices + UNIQUE `(account_id, installment_index)`.
  - **Backfill** vía Python (reusa `build_schedule`): para cada
    liability `loan`/`mortgage` con apr+term+start+opening_balance>0,
    genera las cuotas idempotentemente.
- **`accounts/installments_repository.py`** (nuevo):
  - `generate_installments_for_account(account, *, principal_override=None)`:
    genera las cuotas y persiste. Idempotente. `principal_override`
    permite el flujo PHASE-24 (convert-to-debt) donde el principal
    viene de la tx pareada, no de `opening_balance`.
  - `list_installments` / `get_installment` con aislamiento por user_id.
  - `update_installment_amount_and_date` (override puntual).
  - `mark_installment_paid` / `unmark_installment_paid`.
- **`accounts/service.py`**:
  - `create_account` ahora invoca `generate_installments_for_account`
    para `loan`/`mortgage` con todos los campos del cuadro.
  - `get_amortization_schedule` lee desde la tabla persistida cuando
    hay cuotas; mantiene el fallback on-the-fly (`build_schedule`) para
    cuentas legacy sin cuotas todavía.
  - Nuevos services: `update_installment`, `mark_installment_paid`,
    `unmark_installment_paid` con resolución 404 por aislamiento.
- **`transfers/service.py::convert_to_debt_operation`** (PHASE-24):
  ahora llama a `generate_installments_for_account` con
  `principal_override=source.amount` cuando crea una liability nueva
  con apr+term+start.
- **`accounts/router.py`** — nuevos endpoints:
  - `PATCH /accounts/installments/{id}` — body `{ payment?, due_date? }`.
  - `POST /accounts/installments/{id}/pay` — body `{ paid_at?, paid_transaction_id? }`.
  - `DELETE /accounts/installments/{id}/pay` — vuelve a pendiente.
- **Schema `AmortizationRowResponse`**:
  - Añadido `id`, `paid_at`, `paid_transaction_id` (todos nullable
    para compat con el modo legacy).

### Frontend shared

- `@crisol/types/models/debt.ts`:
  - `AmortizationRow` gana `id?`, `paid_at?`, `paid_transaction_id?`.
  - Nuevos `InstallmentUpdateRequest`, `InstallmentPayRequest`.
- `@crisol/services`:
  - `accountsApi.updateInstallment / payInstallment / unpayInstallment`.
  - Hooks `useUpdateInstallment`, `usePayInstallment`,
    `useUnpayInstallment`. Invalidan `accounts.all` tras éxito.

### Frontend web

- **`app/(app)/personal-finance/accounts/[id]/amortization/page.tsx`**:
  - Header: contador "X / Y pagadas" en vez de solo "Y cuotas".
  - Nueva columna "Estado" en la tabla con dos botones por fila:
    - **Editar** → abre `InstallmentEditDialog` (modal).
    - **Marcar pagada** / **✓ Pagada** → toggle via
      `InstallmentPayButtons`.
  - Filas pagadas con fondo `successSoft` + opacidad ligera.
- **`components/debt/installment-edit-dialog.tsx`** (nuevo): modal con
  inputs de importe + fecha + advertencia "no recomputa las
  siguientes".
- **`components/debt/installment-pay-buttons.tsx`** (nuevo): botón
  pay/unpay compacto con estado loading.

### Frontend mobile

- **`app/(modules)/personal-finance/accounts/[id]/amortization.tsx`**:
  - Cada fila es un `Pressable` con **long-press** para entrar en modo
    edición inline (importe + fecha pasan a `TextInput`).
  - Badge circular pay/unpay (`○` / `✓`) tap para alternar.
  - Filas pagadas con fondo `successSoft`.

### Wizard PHASE-24 retocado

- Default del tipo de cuenta nueva en "Convertir en operación
  financiada": `loan` ("Préstamo / Compra financiada") en vez de
  `credit_card`. Razón: el caso típico (operación financiada de
  BBVA) lleva APR + plazo, que sólo `loan`/`mortgage` aceptan, y por
  tanto sólo esos generan cuotas persistidas y editables.
- Nombre por defecto: "Compra financiada" en vez de "Tarjeta
  financiada".
- `credit_card` se queda como opción para saldo arrastrado sin plan
  fijo (etiqueta "Tarjeta (saldo arrastrado)").

### Tests backend

`tests/test_debt.py` (+4 tests, módulo 17/17):

- `test_create_loan_persists_installments` — crear loan genera N
  cuotas con id estable; suma de principal == principal total.
- `test_patch_installment_overrides_amount_and_date` — PATCH afecta
  sólo a la cuota tocada; las siguientes mantienen los importes
  originales.
- `test_pay_and_unpay_installment` — round-trip de POST/DELETE /pay.
- `test_installment_isolation_between_users` — user B no puede tocar
  cuotas de user A → 404.

Suite completa: **376/376 verde**.

## Flujo técnico

```
Caso A — crear préstamo manualmente
─────────────────────────────────────
POST /accounts { type=loan, opening_balance, apr, term_months, start_date }
    │
    │ create_account persiste la cuenta
    │ → generate_installments_for_account(account)
    │   → build_schedule(principal=opening_balance, ...)
    │   → INSERT N filas en liability_installments
    ▼
GET /accounts/{id}/amortization-schedule
    │ Detecta cuotas persistidas → devuelve filas con id + paid_at + paid_tx_id
    ▼
UI: tabla editable con botones Editar / Marcar pagada por fila

Caso B — convertir tx en operación financiada (PHASE-24)
────────────────────────────────────────────────────────
Detalle de tx → "Convertir en operación financiada" → Crear nueva (loan)
    │ POST /transfers/from-source-debt { new_liability={loan, apr, term, ...}}
    │
    │ _create_liability_for_debt → crea Account(type=loan, opening_balance=0, apr, term, start)
    │ generate_installments_for_account(liability, principal_override=source.amount)
    │   → cuotas con principal = importe financiado (no opening_balance)
    │ Counterpart tx en liability + pair
    ▼
La página de amortización de la nueva liability ya muestra el cuadro editable

Caso C — editar cuota
─────────────────────
UI: "Editar" en la fila 3 → modal con importe + fecha
PATCH /accounts/installments/{id} { payment: "200.00", due_date: "2026-04-05" }
    │ update_installment guarda el override; NO toca las siguientes
    ▼
Refetch: la fila 3 muestra el nuevo importe; saldo pendiente teórico no
recalculado (decisión consciente; se mostraría confuso si propagamos).

Caso D — marcar pagada
──────────────────────
UI: "Marcar pagada" en la fila 1 → POST /accounts/installments/{id}/pay {}
    │ mark_installment_paid asigna paid_at=now(), paid_tx_id=NULL
    ▼
Fila pasa a fondo verde + badge "✓ Pagada"; contador "1 / 12 pagadas".
```

## Archivos clave

Backend:
- `backend/app/modules/personal_finance/accounts/installments_model.py` (nuevo)
- `backend/app/modules/personal_finance/accounts/installments_repository.py` (nuevo)
- `backend/app/modules/personal_finance/accounts/service.py`
- `backend/app/modules/personal_finance/accounts/router.py`
- `backend/app/modules/personal_finance/accounts/schemas.py`
- `backend/app/modules/personal_finance/transfers/service.py`
- `backend/alembic/versions/o2e36g8cb1f9d5_liability_installments.py`

Frontend shared:
- `packages/types/src/models/debt.ts`
- `packages/services/src/api/endpoints/accounts.ts`
- `packages/services/src/query/hooks/useAccounts.ts`

Frontend web:
- `apps/web/app/(app)/personal-finance/accounts/[id]/amortization/page.tsx`
- `apps/web/components/debt/installment-edit-dialog.tsx` (nuevo)
- `apps/web/components/debt/installment-pay-buttons.tsx` (nuevo)
- `apps/web/components/transfers/convert-to-debt-dialog.tsx` (default loan)

Frontend mobile:
- `apps/mobile/app/(modules)/personal-finance/accounts/[id]/amortization.tsx`
- `apps/mobile/components/transfers/convert-to-debt-block.tsx` (default loan)

## Endpoints añadidos

- `PATCH /accounts/installments/{id}` — override puntual.
- `POST /accounts/installments/{id}/pay` — marcar como pagada.
- `DELETE /accounts/installments/{id}/pay` — volver a pendiente.

## Migraciones

- `o2e36g8cb1f9d5_liability_installments.py` — tabla
  `liability_installments` + backfill Python con `build_schedule`
  para liabilities legacy.

## Verificación

- [x] `pytest tests/test_debt.py` — 17/17 verde (4 nuevos PHASE-24.1).
- [x] `pytest` completo — 376/376 verde.
- [x] `pnpm typecheck` — 4/4 verde.
- [x] `pnpm lint` — 4/4 verde.
- [x] `pnpm test` — 46 web + 18 mobile verde.

## Decisiones tomadas

- **Persistir las cuotas (vs calcular siempre)**: necesario para
  almacenar overrides y estado de pago. El coste en BD es trivial
  (~12-360 filas por liability).
- **El override no recomputa las siguientes**: PHASE-24.1 modela
  cuotas como un calendario editable, no como un recalculador. Si el
  usuario quiere recomputar, edita el `opening_balance` / `apr` /
  `term_months` de la cuenta — eso regenera el cuadro (siempre que
  borre las cuotas existentes antes; helper futuro).
- **Modo legacy on-the-fly mantenido**: `get_amortization_schedule`
  cae a `build_schedule` cuando no hay cuotas persistidas. Garantiza
  que cuentas creadas sin amortization (antes de PHASE-22.3 si las
  hay) sigan respondiendo aunque sea con datos calculados sin
  estado.
- **Wizard default `loan`**: el caso BBVA (operación financiada) es
  esencialmente un mini-préstamo con APR + plazo. Modelarlo como
  loan en vez de credit_card permite cuadro editable + KPIs de salud
  financiera correctos.

## Limitaciones conocidas

- Sin auto-match de ADEUDOS importados con cuotas — el usuario debe
  marcar manualmente. PHASE-24.2 lo puede automatizar (match por
  importe + fecha próxima).
- Sin "regenerar cuadro" desde la UI (sólo backfill al crear). Si
  cambias el APR de una cuenta existente, las cuotas quedan
  obsoletas. Workaround actual: borrar la cuenta y recrear.
- Sin selector de tx al marcar pagada (`paid_transaction_id` queda
  NULL desde la UI). La UX para enlazar tx → cuota llega cuando se
  haga el auto-match.

## Próxima fase

PHASE-24.2 (opcional) — auto-match de ADEUDOS importados con cuotas
del cuadro (por importe + ventana de fechas).

PHASE-25 — Cross-currency transfers.
