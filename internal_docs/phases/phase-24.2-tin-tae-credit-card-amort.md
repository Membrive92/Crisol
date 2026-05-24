# PHASE-24.2 — TIN + TAE + tarjetas financiadas con plan fijo

**Estado**: ✅ completada
**Rama**: `feat/phase-24-debt-from-source` (continúa la rama de PHASE-24)
**Fecha de merge**: 2026-05-18

## Objetivo

Dos limitaciones que arrastraba el módulo de deuda:

1. **Sólo se almacenaba un tipo de interés** (`apr`) sin distinguir
   TIN (Tipo de Interés Nominal — el que sirve para calcular cuota)
   de TAE (Tasa Anual Equivalente — informativa, obligatoria por
   regulación bancaria española).

2. **Las tarjetas no aceptaban plan fijo**. Las "tarjetas financiadas"
   de BBVA (compras a plazos con APR + plazo) tenían que registrarse
   como `loan` para tener cuadro, perdiendo la semántica natural de
   "tarjeta".

PHASE-24.2 separa los dos conceptos y permite que `credit_card`
también lleve cuadro francés.

## Qué se implementó

### Backend

- **`accounts/models.py`**: nueva columna `Account.tae` (`Numeric(6,4)`,
  nullable). `apr` se mantiene como nombre interno; en la UI se
  re-etiqueta como "TIN" para alinear con la nomenclatura bancaria
  española.
- **Migración `o2e36g8cb1f9d5` → `p3f47h9dc2g0e6`**: `ALTER TABLE
  accounts ADD COLUMN tae NUMERIC(6,4) NULL`. Sin backfill (NULL
  significa "no declarada", la regulación lo permite mientras se
  conozca el TIN).
- **`accounts/service.py`**:
  - `accepts_amortization = type in {LOAN, MORTGAGE, CREDIT_CARD}`
    (añadido CREDIT_CARD).
  - `get_amortization_schedule` deja de rechazar `credit_card`.
  - `create_account` persiste `tae` cuando aplica.
- **`accounts/schemas.py`**: `AccountCreate`/`Update`/`Response`
  añaden `tae: Decimal | None`. `AmortizationScheduleResponse`
  también devuelve `tae` para que la UI muestre ambos.
- **`transfers/service.py`**:
  - `_LIABILITY_TYPES_AMORT` ahora incluye `credit_card` — el wizard
    "Convertir en operación financiada" genera cuotas también si el
    usuario elige tipo tarjeta.
  - `_create_liability_for_debt` propaga `tae` al crear la liability.
- **`transfers/schemas.py::NewLiabilityForDebt`**: nuevo campo `tae`.

### Frontend shared

- `@crisol/types`:
  - `Account` gana `tae?: string | null`.
  - `AccountCreateRequest`/`AccountUpdateRequest` aceptan `tae`.
  - `AmortizationSchedule.tae` opcional.
  - `NewLiabilityForDebt.tae` opcional.
  - `AMORTIZABLE_ACCOUNT_TYPES` incluye `credit_card`.

### Frontend web

- **`components/accounts/account-form-fields.tsx`**:
  - `AccountFormValue` gana `tae_percent`.
  - Inputs renombrados: "APR anual (%)" → **"TIN anual (%)"** + nuevo
    input **"TAE anual (%) opc."**.
  - Texto explicativo actualizado para diferenciar ambos conceptos.
- **`app/(app)/settings/accounts/page.tsx`**: serializa/deserializa
  `tae_percent` ↔ `tae` decimal en payloads create/update.
- **`components/transfers/convert-to-debt-dialog.tsx`**:
  - Tres inputs en la sección de amortización: **TIN**, **TAE opc.**,
    **Plazo (meses)**.
  - `acceptsAmortization` ahora siempre true (cualquier tipo de deuda
    acepta plan).
- **`app/(app)/personal-finance/accounts/[id]/amortization/page.tsx`**:
  KPI "Plazo restante" footer ahora muestra "X meses · TIN Y%" más
  "· TAE Z%" si está declarada.

### Frontend mobile

- **`components/accounts/account-form-modal.tsx`**:
  - `AccountFormValues` gana `tae_percent`.
  - Tres inputs apilados: **TIN**, **TAE opc.**, **Plazo**.
- **`app/(modules)/personal-finance/accounts.tsx`**: serializa
  `tae_percent` → `payload.tae` en create + update.
- **`components/transfers/convert-to-debt-block.tsx`**: tres inputs en
  fila (TIN / TAE / Plazo) cuando se crea una deuda nueva.
- **`app/(modules)/personal-finance/accounts/[id]/amortization.tsx`**:
  footer del KPI muestra ambos porcentajes.

### Tests backend

`tests/test_debt.py`:

- **Reemplazado** `test_amortization_fields_ignored_for_non_loan_types`
  → `test_amortization_fields_accepted_for_credit_card`: tarjetas sí
  aceptan APR/term/start; cuentas asset (bank) siguen
  descartándolos.
- **Nuevo** `test_create_credit_card_with_amortization_persists_installments`:
  una tarjeta con apr+term+start genera N cuotas igual que un loan.
- **Nuevo** `test_account_tae_is_persisted_and_returned`: round-trip
  de TAE en create + update.

Suite completa: **378/378 verde**.

## Flujo técnico

```
Caso A — operación financiada BBVA (824,77€, 12 cuotas, TIN 7.95%, TAE 8.24%)
────────────────────────────────────────────────────────────────────────────
Detalle de tx → "Convertir en operación financiada" → Crear nueva
    │ Tipo: "Tarjeta de crédito" (o Préstamo)
    │ TIN: 7.95 (% UI → 0.0795 decimal en payload)
    │ TAE: 8.24 (% UI → 0.0824 decimal en payload)
    │ Plazo: 12
    │
    │ POST /transfers/from-source-debt {
    │   new_liability: {
    │     name: "Tarjeta financiada", type: "credit_card",
    │     apr: "0.0795", tae: "0.0824", term_months: 12
    │   }
    │ }
    │
    │ _create_liability_for_debt:
    │   accepts_amortization = true (credit_card también)
    │   Account.apr=0.0795, Account.tae=0.0824, Account.term_months=12
    │
    │ generate_installments_for_account(account, principal_override=824.77)
    │   → 12 cuotas con interest calculado desde apr/12 (TIN)
    ▼
GET /accounts/{id}/amortization-schedule
    │ Devuelve principal + apr (TIN) + tae + rows
    ▼
UI muestra:
- KPIs con cuota mensual, intereses totales, total a pagar
- Footer del plazo: "12 meses · TIN 7.95% · TAE 8.24%"
- Tabla de 12 cuotas editables y marcables como pagadas (PHASE-24.1)
```

## Archivos clave

Backend:
- `backend/app/modules/personal_finance/accounts/{models,schemas,service}.py`
- `backend/app/modules/personal_finance/transfers/{schemas,service}.py`
- `backend/alembic/versions/p3f47h9dc2g0e6_account_tae_and_credit_card_amort.py`

Frontend shared:
- `packages/types/src/models/{account,debt}.ts`
- `packages/types/src/dto/{account,transfer}.dto.ts`

Frontend web:
- `apps/web/components/accounts/account-form-fields.tsx`
- `apps/web/app/(app)/settings/accounts/page.tsx`
- `apps/web/components/transfers/convert-to-debt-dialog.tsx`
- `apps/web/app/(app)/personal-finance/accounts/[id]/amortization/page.tsx`

Frontend mobile:
- `apps/mobile/components/accounts/account-form-modal.tsx`
- `apps/mobile/app/(modules)/personal-finance/accounts.tsx`
- `apps/mobile/components/transfers/convert-to-debt-block.tsx`
- `apps/mobile/app/(modules)/personal-finance/accounts/[id]/amortization.tsx`

## Migraciones

- `p3f47h9dc2g0e6_account_tae_and_credit_card_amort.py` — añade
  columna `accounts.tae` nullable. Sin backfill.

## Verificación

- [x] `pytest tests/test_debt.py` — 19/19 verde (+2 PHASE-24.2).
- [x] `pytest` completo — 378/378 verde.
- [x] `pnpm typecheck` — 4/4 verde.
- [x] `pnpm lint` — 4/4 verde.
- [x] `pnpm test` — 46 web + 18 mobile verde.

## Decisiones tomadas

- **`apr` se mantiene como nombre interno** (column + field) — el
  rename a `tin` sería invasivo y `apr` está atrincherado en
  migraciones previas. El re-labeling es sólo de UI.
- **TAE es opcional**: la regulación obliga a declararla a los bancos,
  pero el usuario que registra su propia deuda puede no conocerla.
  NULL es válido.
- **TAE no afecta al cálculo**: el sistema francés se computa con
  el TIN mensualizado (`apr / 12`). TAE es puramente informativa
  para que el usuario contraste con lo que firmó.
- **`credit_card` amortizable por defecto en el wizard**: el caso
  típico (compra a plazos BBVA) modela mejor como "tarjeta
  financiada" semánticamente que como "préstamo". Antes forzábamos
  loan; ahora se respeta la intención del usuario.
- **No autoderivar TAE desde TIN**: hay fórmulas (depende de
  capitalización + comisiones), pero requeriría asumir un esquema
  de comisiones. El usuario introduce el valor que su banco le
  declara.

## Limitaciones conocidas

- No hay validación cruzada `TAE >= TIN` (debería serlo siempre,
  porque TAE incluye comisiones). La UI lo permite por flexibilidad
  — caso real: una promoción puntual sin comisiones donde TAE = TIN.
- Cross-currency sigue sin soportarse (heredado de PHASE-23.1/24).

## Próxima fase

PHASE-24.3 (opcional) — Auto-match de ADEUDOS importados con cuotas
del cuadro (por importe + ventana de fechas), o PHASE-25 — Cross-
currency transfers.
