# PHASE-24.3 — Total a pagar + comisiones derivadas dinámicamente

**Estado**: ✅ completada
**Rama**: `feat/phase-24-debt-from-source` (continúa la rama de PHASE-24)
**Fecha de merge**: 2026-05-19

## Objetivo

La pantalla "Datos de la financiación" de BBVA muestra:

```
Primer pago (sólo intereses)    0,00 €
Resto de cuotas                 9 x 100,08 €
Periodo cuotas                  05/03/2026 – 05/11/2026
TIN                             21,60 %
TAE                             24,12 %
Total a pagar                   913,86 €
```

Pero la suma de las 9 cuotas (`9 × 100,08 = 900,72€`) no cuadra con
el total. Hay **13,14€ de comisiones que el banco no desglosa pero
sí incluye en el total**. El delta TAE–TIN compuesto (24,12% vs
23,87%) corrobora que hay coste extra.

PHASE-24.3 permite registrar **el total tal cual lo da el banco** y
**deriva la comisión dinámicamente** restándolo al cuadro teórico.
Así el saldo y los KPIs cuadran con la app bancaria al céntimo.

## Qué se implementó

### Backend

- **Modelo `Account`** (PHASE-24.3): dos campos nuevos
  - `total_to_pay: Decimal | None` — total contractualizado
  - `interest_only_first_payment: Decimal | None` — primera cuota
    especial que sólo paga intereses (cuando el contrato no arranca
    alineado con la fecha de cuota). 0€ en la mayoría de los casos.
- **Migración `q4g58i0ed3h1f7`**: `ALTER TABLE accounts ADD COLUMN
  total_to_pay`, `ADD COLUMN interest_only_first_payment` (ambas
  `NUMERIC(14,2) NULL`).
- **`AmortizationScheduleResponse`** expone:
  - `total_to_pay` (informativo)
  - `interest_only_first_payment` (informativo)
  - `extra_charges` (derivado: `total_to_pay − total_paid − interest_only`)
- **`accounts/service.py::_compute_extra_charges`**: helper puro que
  computa el derivado. Devuelve `None` si `total_to_pay` no está
  declarado. NO corregimos a negativo: si total_to_pay < total_paid,
  lo dejamos visible para que el usuario revise.
- **`accounts/service.py::create_account`**: persiste los nuevos
  campos cuando `accepts_amortization`.
- **`transfers/service.py::_create_liability_for_debt`**: propaga
  `total_to_pay` y `interest_only_first_payment` desde
  `NewLiabilityForDebt`.

### Cambio de algoritmo en `build_schedule` (importante)

Antes el último mes ajustaba el `payment` (no el `principal`) para
cerrar el saldo a 0 — eso hacía que la última cuota fuera ligeramente
distinta (ej. 100,13€ vs 100,08€). Resultado: `Σ payments = 900,77€`
en lugar de los 900,72€ que muestra BBVA.

Ahora **todas las cuotas tienen el mismo `payment` exacto** (la
constante francesa redondeada). El residuo de céntimos se absorbe en
el `principal` del último mes. Esto:
1. Hace que `Σ payments = n × payment` cuadre al céntimo con la
   presentación del banco.
2. Permite que `extra_charges` refleje EXACTAMENTE la comisión que
   cobra BBVA, sin offsets de redondeo.

### Frontend shared

- `@crisol/types`:
  - `Account` gana `total_to_pay?`, `interest_only_first_payment?`.
  - `AccountCreateRequest`/`UpdateRequest` los aceptan.
  - `AmortizationSchedule` gana `total_to_pay?`,
    `interest_only_first_payment?`, `extra_charges?`.
  - `NewLiabilityForDebt` los acepta también.

### Frontend web

- **`components/accounts/account-form-fields.tsx`**: en la sección
  "Cuadro de amortización" se añaden dos inputs:
  - **Total a pagar (€) opc.** — pega el valor del banco.
  - **1er pago sólo intereses (€) opc.** — casi siempre 0.
  - Texto explicativo: "destaparemos como cargos extra cualquier
    diferencia con el cuadro teórico".
- **`app/(app)/settings/accounts/page.tsx`**: serializa/deserializa
  ambos campos en create + update.
- **`components/transfers/convert-to-debt-dialog.tsx`**: input
  adicional "Total a pagar" en el wizard de conversión.
- **`app/(app)/personal-finance/accounts/[id]/amortization/page.tsx`**:
  el KPI "Total a pagar" ahora:
  - Muestra `total_to_pay` si está informado (label "Total a pagar
    (banco)").
  - Si no, muestra `total_paid` calculado (label "Total a pagar
    (cuadro)").
  - Footer revela los `extra_charges` cuando ≠ 0:
    "Incluye 13,14€ de cargos extra no desglosados".

### Frontend mobile

- **`components/accounts/account-form-modal.tsx`**: dos inputs nuevos
  en la sección de amortización.
- **`app/(modules)/personal-finance/accounts.tsx`**: paridad en
  serialize/deserialize.
- **`components/transfers/convert-to-debt-block.tsx`**: input "Total a
  pagar" en el bloque de conversión.
- **`app/(modules)/personal-finance/accounts/[id]/amortization.tsx`**:
  KPI con label dinámico + footer "+X€ cargos extra".

### Tests backend

`tests/test_debt.py` (+2 tests, módulo 21/21):

- `test_extra_charges_derived_from_total_to_pay`: caso BBVA exacto
  (824,77€ · 21,6% · 9 cuotas · 913,86€) → `extra_charges = 13,14€`.
- `test_extra_charges_null_when_total_to_pay_not_set`: sin
  total_to_pay, no inventamos cargos.

Suite completa: **380/380 verde**.

## Flujo técnico

```
Usuario abre el detalle de su tarjeta financiada BBVA → Editar
    │ Rellena (copia del extracto del banco):
    │   Capital: 824,77€
    │   TIN: 21,60% · TAE: 24,12%
    │   Plazo: 9 meses · Fecha inicio: 05/02/2026
    │   Total a pagar (€): 913,86
    │   1er pago sólo intereses: 0,00
    ▼
PATCH /accounts/{id} → guarda los 6 campos
    │
    │ Cuotas ya generadas (PHASE-24.1) con build_schedule:
    │   9 cuotas exactas de 100,08€ → Σ = 900,72€
    │
    ▼
GET /accounts/{id}/amortization-schedule
    │ Devuelve:
    │   monthly_payment: 100,08
    │   total_paid: 900,72  (teórico, Σ cuotas)
    │   total_to_pay: 913,86  (informado por usuario)
    │   interest_only_first_payment: 0,00
    │   extra_charges: 913,86 − 900,72 − 0,00 = 13,14  ←  ¡aflora!
    ▼
UI muestra:
- KPI "Total a pagar (banco)": 913,86€
  Footer: "Incluye 13,14€ de cargos extra no desglosados"
- Tabla de cuotas: 9 × 100,08€ (editables, marcables como pagadas)
- TIN 21,6% · TAE 24,12% (footer del KPI de plazo)

Saldo de la cuenta liability:
- opening_balance: 0 (creada via convert-to-debt)
- counterpart tx: +824,77€
- current_balance: 824,77€  ←  igual al "Importe pendiente" inicial BBVA
```

## Archivos clave

Backend:
- `backend/app/modules/personal_finance/accounts/{models,schemas,service}.py`
- `backend/app/modules/personal_finance/accounts/amortization.py` (algoritmo)
- `backend/app/modules/personal_finance/transfers/{schemas,service}.py`
- `backend/alembic/versions/q4g58i0ed3h1f7_account_total_to_pay_interest_only.py`

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

- `q4g58i0ed3h1f7_account_total_to_pay_interest_only.py` — añade
  `accounts.total_to_pay` y `accounts.interest_only_first_payment`,
  ambos nullable. Sin backfill.

## Verificación

- [x] `pytest tests/test_debt.py` — 21/21 verde (+2 PHASE-24.3).
- [x] `pytest` completo — 380/380 verde.
- [x] `pnpm typecheck` — 4/4 verde.
- [x] `pnpm lint` — 4/4 verde.
- [x] `pnpm test` — 46 web + 18 mobile verde.

## Decisiones tomadas

- **`extra_charges` derivado, no almacenado**: lo computamos en cada
  respuesta del schedule. Esto evita inconsistencia si cambias TIN o
  cuotas pero olvidas refrescar el cargo.
- **El algoritmo `build_schedule` ahora mantiene cuota constante
  exacta**. El residuo de redondeo se acumula en el `principal` del
  último mes (típicamente ±0,05€), no en el `payment`. Esto alinea
  nuestra presentación con la del banco ("9 × 100,08€" exacto).
- **`extra_charges` puede ser negativo**: si el usuario informa un
  `total_to_pay` menor que el cuadro teórico, mostramos la
  diferencia negativa. Probablemente indica que TIN/plazo están
  mal — el usuario decide qué corregir.
- **No automatizamos la conversión TAE → TIN ni viceversa**: hay
  fórmulas, pero dependen del esquema de comisiones de cada banco.
  El usuario introduce ambos valores tal cual los lee del contrato.

## Limitaciones conocidas

- El `interest_only_first_payment` está modelado pero no se inserta
  como cuota separada en la tabla `liability_installments`. Sólo
  participa en el cálculo de `extra_charges`. Para casos donde es
  no-cero y se quiera ver como una cuota más, queda como
  follow-up.
- Sigue sin existir cross-currency (PHASE-25).

## Próxima fase

PHASE-25 — Cross-currency transfers, o PHASE-24.4 — Auto-match de
ADEUDOS importados con cuotas del cuadro.
