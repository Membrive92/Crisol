# PHASE-24 — Operaciones financiadas (deuda con plan de pago)

**Estado**: ✅ completada
**Rama**: `feat/phase-24-debt-from-source`
**Fecha de merge**: 2026-05-17

## Objetivo

Cuando el banco ofrece compras a plazos o préstamos, el extracto
muestra un abono (ingreso aparente) en la cuenta corriente y luego va
cobrando cuotas mensuales (gastos aparentes). Hasta esta fase, Crisol
trataba ambos como cashflow real:
- El abono inflaba ingresos (gasto invertido en un préstamo se veía
  como dinero entrante).
- Cada cuota mensual se contaba como gasto adicional (cuando en
  realidad es devolución de la deuda original).

PHASE-24 modela esto correctamente como una **operación financiada**:
el abono inicial queda emparejado con la creación de una **cuenta de
deuda** (liability), y las cuotas posteriores pueden enlazarse a esa
deuda con el mecanismo de transferencias existente (PHASE-21.3 /
PHASE-23.1). La deuda crece/decrece en su propio saldo y queda fuera
del cashflow agregado.

## Qué se implementó

### Backend

- **`transfers/schemas.py`** — nuevos schemas:
  - `NewLiabilityForDebt`: subset de `AccountCreate` con
    `name`/`type`/`currency`/`color`/`icon`/`apr`/`term_months`/
    `start_date`. Tipo restringido a `credit_card` | `loan` |
    `mortgage`.
  - `TransferFromSourceDebtRequest`: `source_transaction_id` +
    EITHER `destination_account_id` (liability existente) OR
    `new_liability` (crear al vuelo).
- **`transfers/service.py`**:
  - `convert_to_debt_operation(...)`: orquesta el flujo.
    1. Valida origen (existe, no pareada).
    2. Valida XOR entre `destination_account_id` y `new_liability`.
    3. Si new_liability → `_create_liability_for_debt` crea la cuenta
       con nature=LIABILITY (validando tipo permitido y unicidad de
       nombre; campos de amortización sólo para `loan`/`mortgage`).
    4. Si existing → valida que es liability + misma moneda.
    5. Crea contraparte en la liability: kind=EXPENSE (hace que la
       deuda suba: liability+expense → +amount en balance).
    6. Empareja vía `transfer_pair_id`.
- **`transfers/router.py`**: `POST /transfers/from-source-debt`.

### Frontend shared

- `@crisol/types`:
  - `NewLiabilityForDebt`, `TransferFromSourceDebtRequest`.
- `@crisol/services`:
  - `transfersApi.fromSourceDebt(payload)`.
  - `useConvertToDebt()` (mutation). Tras éxito invalida transfers +
    transactions + dashboard + budgets + accounts (puede haberse
    creado una nueva liability).

### Frontend web

- **`components/transfers/convert-to-debt-dialog.tsx`** (nuevo): Card
  en el detalle de tx con dos pestañas:
  - **Usar deuda existente**: dropdown de cuentas liability del
    usuario en la misma moneda.
  - **Crear nueva**: TextInput nombre, Select tipo
    (credit_card/loan/mortgage), si tipo es loan/mortgage muestra
    APR + plazo (la fecha se hereda de la tx origen).
- Exporta también `looksLikeFinancedOperation(description)` —
  heurística que matchea "operacion financiada" / "operación
  financiada" / "operacion fraccionada" / "tarjeta financiada" /
  "compra a plazos" (case-insensitive, con y sin tildes).
- **`app/(app)/personal-finance/transactions/[id]/page.tsx`**: el
  diálogo se renderiza sólo cuando la tx no está emparejada Y la
  descripción matchea la heurística — así no añade ruido visual a
  cualquier tx.
- **`components/imports/preview-step.tsx`**: badge "Posible deuda"
  (color warning) junto a la descripción en el preview cuando la
  heurística matchea. El badge es informativo — la conversión real se
  hace tras confirmar el import, desde el detalle de la tx.

### Frontend mobile

- **`components/transfers/convert-to-debt-block.tsx`**: equivalente
  mobile con chips en lugar de dropdowns, mismos campos y flujo.
- **`app/(modules)/personal-finance/transaction/[id].tsx`**: monta el
  block bajo el formulario cuando aplica.

### Tests backend

Añadidos a `tests/test_transfers.py` (6 tests, total módulo 26/26):

- `from-source-debt` con `new_liability` crea la cuenta liability +
  contraparte + balances correctos + cashflow 0.
- `from-source-debt` con `destination_account_id` existente reusa la
  cuenta sin crear nada nuevo.
- 400 si destino es asset (no liability).
- 400 si ninguno de los dos viene (XOR).
- 400 si `new_liability.type` es asset (ej. `bank`).
- Campos de amortización (apr/term/start_date) se persisten en
  cuentas `loan`.

Suite completa: **372/372 verde**.

## Flujo técnico

```
BBVA recibe +824,77€ "OPERACION FINANCIADA CON TARJETA"
    │
    │ Usuario abre el detalle de la tx
    │ La descripción matchea looksLikeFinancedOperation()
    │ → aparece la card "¿Es una operación financiada?"
    │
    │ Tab "Crear nueva" → name="Tarjeta financiada BBVA",
    │ type=credit_card → submit
    ▼
POST /transfers/from-source-debt
    │ Validaciones (origen, XOR, tipo destino)
    │
    │ _create_liability_for_debt → crea Account(
    │   name="Tarjeta financiada BBVA",
    │   type=CREDIT_CARD, nature=LIABILITY,
    │   currency=EUR (heredada de source),
    │ )
    │
    │ Counterpart en la liability:
    │   amount=824.77, currency=EUR, occurred_at=mismo
    │   category="Transferencia interna (salida)" (is_transfer=true, EXPENSE)
    │   description="Deuda contraída desde BBVA"
    │   source=MANUAL
    │
    │ link_pair(source, counterpart) → transfer_pair_id bidireccional
    │
    ▼
Saldos:
- BBVA: +824,77 (sigue ahí, el dinero realmente entró)
- Tarjeta financiada (liability): +824,77 (deuda contraída)
- Patrimonio neto: +824,77 asset − 824,77 deuda = 0

Cashflow agregado:
- expenses=0, income=0 (par emparejado excluido)

Para las cuotas mensuales (ADEUDO MENSUAL DE TARJETA):
- Cada cuota es un gasto en BBVA + reducción de deuda en la liability
- El usuario las convierte usando el flujo de transferencia
  existente (PHASE-23.1: "Convertir en transferencia" con destino =
  la cuenta de deuda)
- Resultado: -amount en BBVA, -amount en liability (paga deuda)
```

## Archivos clave

Backend:
- `backend/app/modules/personal_finance/transfers/schemas.py`
- `backend/app/modules/personal_finance/transfers/service.py`
- `backend/app/modules/personal_finance/transfers/router.py`

Frontend shared:
- `packages/types/src/dto/transfer.dto.ts`
- `packages/services/src/api/endpoints/transfers.ts`
- `packages/services/src/query/hooks/useTransfers.ts`

Frontend web:
- `apps/web/components/transfers/convert-to-debt-dialog.tsx`
- `apps/web/app/(app)/personal-finance/transactions/[id]/page.tsx`
- `apps/web/components/imports/preview-step.tsx`

Frontend mobile:
- `apps/mobile/components/transfers/convert-to-debt-block.tsx`
- `apps/mobile/app/(modules)/personal-finance/transaction/[id].tsx`

## Endpoints añadidos

- `POST /transfers/from-source-debt` — convierte tx en operación
  financiada, opcionalmente creando la cuenta de deuda al vuelo.

## Migraciones

Ninguna — reutiliza tablas existentes (`accounts` ya tiene
`apr`/`term_months`/`start_date` desde PHASE-22.3 y `transactions`
ya tiene `transfer_pair_id` desde PHASE-21.3).

## Verificación

- [x] `pytest tests/test_transfers.py` — 26/26 verde (+6 nuevos
      PHASE-24).
- [x] `pytest` completo — 372/372 verde.
- [x] `pnpm typecheck` — 4/4 verde.
- [x] `pnpm lint` — 4/4 verde.
- [x] `pnpm test` — 46 web + 18 mobile verde.

## Decisiones tomadas

- **Reutilizar `transfer_pair_id`** en lugar de modelar deuda como
  un concepto independiente: la operación financiada ES una
  transferencia interna especial (de asset a liability). Misma
  mecánica de exclusión de cashflow.
- **Heurística sólo en frontend** para mostrar el botón. El backend
  no inspecciona descripciones — acepta cualquier tx como candidata.
  Razón: la heurística es UX, no validación; el backend debe seguir
  siendo flexible.
- **No automatizar la categorización de cuotas mensuales** en esta
  fase. Cuando el usuario importa una cuota ADEUDO MENSUAL, sigue
  llegando como gasto normal en BBVA — el usuario la convierte
  manualmente con "Convertir en transferencia" (PHASE-23.1)
  apuntando a la liability. Auto-detección queda como follow-up.
- **El badge "Posible deuda" en el preview de import no actúa** —
  sólo flagea visualmente. El usuario revisa después del import. Esto
  evita decisiones implícitas durante el wizard.

## Limitaciones conocidas

- Cross-currency no soportado (mismo límite que PHASE-23.1).
- No hay UX para "convertir bulk" un batch de operaciones financiadas
  detectadas en el import — una a una desde el detalle.
- La detección de cuotas mensuales (ADEUDO) que corresponden a una
  operación financiada concreta no es automática. Si el usuario tiene
  varias deudas activas, debe elegir manualmente a cuál pagar cada
  cuota.

## Próxima fase

PHASE-25 — Cross-currency transfers (origen y destino en distintas
monedas, conversión vía rates del día).
