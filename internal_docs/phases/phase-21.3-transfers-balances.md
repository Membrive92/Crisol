# PHASE-21.3 — Transferencias internas + saldos por cuenta + patrimonio neto + filtro por cuenta

**Estado**: ✅ completada
**Rama**: directo a `main`
**Commit**: `16ca819`
**Fecha de merge**: 2026-05-10

## Objetivo

Resolver el problema raíz que motivó el sprint: las transferencias
internas (mover dinero de cuenta corriente a cuenta de ahorro o al
broker) inflaban gastos e ingresos por igual, distorsionando el
flujo neto y la tasa de ahorro. Esta fase modela las transferencias
como pares de transacciones enlazadas y las excluye de los
agregados de cashflow. Además expone el saldo de cada cuenta y un
agregado de patrimonio neto.

## Qué se implementó

### Backend — módulo `transfers`

`backend/app/modules/personal_finance/transfers/`:

- **`schemas.py`** — `TransferPair`, `TransferCandidate`,
  `TransferLinkRequest`, `TransferMatchOptions` (con `window_days`
  configurable), `TransferMatchResponse` (linked + pending).
- **`repository.py`** — `find_candidate_pairs(items, window_days)`
  recorre las txs no emparejadas y propone pares por:
  - mismo `amount` (Decimal exacto)
  - misma `currency`
  - cuentas distintas (`account_id` diferente)
  - `occurred_at` dentro de `±window_days`
  - kind opuesto (income vs expense) — txs sin categoría caen en
    "unknown" y entran en ambos pools.
  Cada tx aparece como mucho en UN par; ambigüedades se resuelven
  por proximidad de fecha y luego por id determinista.
  `filter_unambiguous` separa los pares con huella única
  (`amount + currency + frozenset({acc_a, acc_b})`) de los que
  comparten huella.
- **`service.py`** — `auto_match` enlaza los unambiguous y devuelve
  los ambiguous. `link_manually` valida (cuentas distintas, mismo
  amount/currency, ninguna ya emparejada) y enlaza. `unlink` rompe
  el par.
- **`router.py`** — `GET /transfers`, `GET /transfers/candidates`,
  `POST /transfers/match`, `POST /transfers/link`,
  `DELETE /transfers/{transaction_id}`.

### Backend — `transfer_pair_id` + exclusión en agregados

- **`Transaction.transfer_pair_id`** — FK auto-referente a
  `transactions(id)` `ON DELETE SET NULL`, nullable. Bidireccional:
  al emparejar A con B, A.transfer_pair_id = B.id Y B.transfer_pair_id = A.id.
- **Exclusión en `_apply_scope`** del dashboard repository:
  cualquier query que pase por ahí (summary, by_category, top_expenses)
  añade `WHERE transfer_pair_id IS NULL`. Igual en `get_totals_by_month`.
- **Exclusión en budgets** (`sum_expenses_in_period`): una
  transferencia interna no consume presupuesto.

### Backend — saldos por cuenta (PHASE-19.4 absorbida aquí)

- **`accounts/repository.py::get_balances_for_user`** —
  `signed_amount = CASE expense → -amount, income → +amount,
  ELSE +amount`. Suma agrupando por `account_id`, sólo txs en la
  moneda nativa de la cuenta, excluye papelera. Las transferencias
  SÍ cuentan al saldo individual (tienen su `account_id` y siguen
  siendo income/expense desde el punto de vista del kind).
- **`accounts/service.py::get_balances`** —
  `current_balance = opening_balance + movements_balance`. Cuentas
  archivadas vienen en `items` pero no suman a `total_assets` /
  `total_liabilities`. Si las cuentas activas no son monomoneda,
  `mixed_currencies=true` y los totales son suma cruda
  (la UI debe avisar).
- **`GET /accounts/balances`** — endpoint nuevo.

### Backend — filtro `account_id` en transactions

`Transaction list` (`/transactions?account_id=...`): nuevo query
param que pasa por `_scope` del repository. Compatible con todos
los demás filtros existentes.

### Frontend — types/services/hooks

- `packages/types/src/models/transfer.ts` (TransferPair,
  TransferCandidate, TransferMatchResponse) +
  `account-balance.ts` (AccountBalance, AccountBalancesResponse) +
  `dto/transfer.dto.ts`.
- `Transaction.transfer_pair_id`, `TransactionListQuery.account_id`.
- `transfersApi`, `accountsApi.balances()`.
- `useTransfers`, `useTransferCandidates(windowDays)`,
  `useMatchTransfers`, `useLinkTransfer`, `useUnlinkTransfer`,
  `useAccountBalances`. Las mutaciones invalidan transactions +
  dashboard + budgets + balances cuando cambian.

### Frontend web

- `apps/web/app/(app)/personal-finance/transfers/page.tsx` —
  pantalla con cabecera "Detectar automáticas", lista de pares
  activos (con "Deshacer") y sección colapsable "Sugerencias
  pendientes" (con "Enlazar").
- `apps/web/components/transfers/transfer-pair-card.tsx` — card
  reusable que renderiza tanto `TransferPair` como `TransferCandidate`.
- `apps/web/components/accounts/balances-card.tsx` — patrimonio
  neto + activos/pasivos + lista de cuentas activas con
  `current_balance`. Warning si `mixed_currencies`. Variantes
  `full` y `compact`.
- `apps/web/app/(app)/personal-finance/analysis/page.tsx` — monta
  `BalancesCard` arriba.
- `apps/web/app/(app)/settings/accounts/page.tsx` — cada fila
  muestra `current_balance`.
- `apps/web/app/(app)/personal-finance/transactions/page.tsx`
  + `apps/web/components/transactions/stitch-search-toolbar.tsx`
  — selector "Cuenta" en filtros.
- `apps/web/components/transactions/transaction-list.tsx` —
  badge "Transferencia" en filas con `transfer_pair_id`; acción
  inline "Deshacer".
- `packages/types/src/registry/modules.ts` — sección `transfers`
  añadida al registry para que el sidebar la liste.

### Frontend mobile

- `apps/mobile/app/(modules)/personal-finance/transfers.tsx` —
  espejo de la pantalla web.
- `apps/mobile/components/transfers/transfer-pair-card.tsx`.
- `apps/mobile/components/accounts/balances-card.tsx` —
  `BalancesCard` con `Modal` nativo cuando hace falta.
- `apps/mobile/app/(modules)/personal-finance/(tabs)/analysis.tsx`
  — monta `BalancesCard` y añade link "Transferencias".
- `apps/mobile/app/(modules)/personal-finance/(tabs)/transactions.tsx`
  — picker de cuenta + badge "Transferencia".
- `apps/mobile/app/(modules)/personal-finance/accounts.tsx` —
  `current_balance` en cada fila.
- `apps/mobile/app/(modules)/personal-finance/_layout.tsx` —
  registra la `transfers` Stack.Screen.

## Flujo técnico

```
 Usuario tiene una salida en BBVA (-500€) y una entrada en Broker (+500€)
    │ Ambas existen como Transaction independientes
    ▼
 Va a /personal-finance/transfers → "Detectar automáticas"
    │
 POST /transfers/match { window_days: 3 }
    │ list_unmatched_active_transactions(user_id)
    │ find_candidate_pairs(items, window_days=3)
    │ filter_unambiguous(pairs)
    │ for each unambiguous: link_pair (bidireccional)
    │ → response: { linked_count: 1, pending_candidates: [] }
    ▼
 Frontend invalida: transfers + transactions + dashboard + budgets
    + balances
    ▼
 Cashflow:
    │ Antes: income +500, expense -500 (suma cero pero infla volumen)
    │ Ahora: WHERE transfer_pair_id IS NULL → ambas excluidas
    │ Resultado: income 0, expense 0
 Saldo por cuenta:
    │ BBVA: opening + Σ(income−expense) en EUR → bajó 500
    │ Broker: opening + Σ(income−expense) en EUR → subió 500
    │ Patrimonio neto: total_assets sin cambio
```

## Archivos clave

### Backend
- `backend/app/modules/personal_finance/transfers/` (módulo nuevo)
- `backend/alembic/versions/k8a92c4e7d5a1_transfers_pair.py`
- `backend/app/modules/personal_finance/transactions/{models,schemas}.py`
  (`transfer_pair_id`)
- `backend/app/modules/personal_finance/dashboard/repository.py`
  (exclusión transfer en `_apply_scope` y `get_totals_by_month`)
- `backend/app/modules/personal_finance/budgets/repository.py`
  (exclusión transfer en `sum_expenses_in_period`)
- `backend/app/modules/personal_finance/accounts/{repository,service,schemas,router}.py`
  (balances)
- `backend/tests/test_transfers.py` (módulo nuevo, 11 tests)
- `backend/app/main.py` (registra `transfers_router`)

### Frontend
- `packages/types/src/models/{transfer,account-balance}.ts`,
  `packages/types/src/dto/transfer.dto.ts`
- `packages/services/src/api/endpoints/transfers.ts`,
  `packages/services/src/query/hooks/useTransfers.ts`
- `apps/web/app/(app)/personal-finance/transfers/page.tsx`
- `apps/web/components/transfers/transfer-pair-card.tsx`
- `apps/web/components/accounts/balances-card.tsx`
- `apps/mobile/app/(modules)/personal-finance/transfers.tsx`
- `apps/mobile/components/transfers/transfer-pair-card.tsx`
- `apps/mobile/components/accounts/balances-card.tsx`

## Endpoints añadidos

- `GET /transfers` — pares activos del usuario.
- `GET /transfers/candidates?window_days=N` — sugerencias del
  matcher sin escribir nada en BD.
- `POST /transfers/match` — auto-link de unambiguous + devolver
  ambiguous para revisión manual.
- `POST /transfers/link { out_transaction_id, in_transaction_id }`
  — enlace explícito.
- `DELETE /transfers/{transaction_id}` — deshacer par.
- `GET /accounts/balances` — saldo por cuenta + agregados de
  patrimonio.
- `GET /transactions?account_id=` — filtro por cuenta.

## Migraciones

- `k8a92c4e7d5a1_transfers_pair.py` — `ADD COLUMN transfer_pair_id
  UUID NULL` en `transactions` + FK auto-referente
  `ON DELETE SET NULL` + index parcial
  `WHERE transfer_pair_id IS NOT NULL AND deleted_at IS NULL`.
  Sin wipe — la columna queda en NULL en todas las txs existentes
  (comportamiento idéntico al de antes hasta que el usuario empareje).

## Verificación

- [x] `pytest backend/tests/` verde (344 tests, +11 nuevos).
- [x] `pnpm typecheck`, `pnpm lint`, `pnpm test` verdes (45 web
      + 18 mobile).
- [x] Migración aplicada en BD local sin errores.
- [x] Smoke manual:
  - [x] Crear salida 500€ en BBVA + entrada 500€ en broker → match
        automático las enlaza.
  - [x] Tras emparejar, summary del dashboard pasa de
        `income=500, expense=500` a `income=0, expense=0`.
  - [x] BalancesCard muestra el saldo correcto por cuenta.
  - [x] `/transactions?account_id=X` devuelve sólo las de esa cuenta.
  - [x] Aislamiento multi-tenant: usuario B no puede ver/enlazar
        pares del usuario A.

## Decisiones tomadas

- **Modelo de pares en lugar de tercer `kind`**. Discutido en chat:
  un `kind=transfer` requeriría reorganizar el signo del amount
  (in vs out). El modelo de pares preserva la semántica actual
  (income suma, expense resta) y enlaza dos txs reales. Cada
  movimiento sigue siendo income o expense en su cuenta — sólo
  que se excluye del flujo neto cuando está emparejado.
- **Política conservadora del matcher**. Si hay dos salidas y dos
  entradas idénticas (mismo amount/currency entre las mismas
  cuentas), NO enlaza nada: las cuatro quedan como pending y el
  usuario decide. Evita emparejar mal.
- **`window_days=3` por defecto**. Cubre el caso típico del banco
  que carga el día siguiente o tras fin de semana. Configurable
  via body de `/transfers/match`.
- **Bidireccional al enlazar**. A.transfer_pair_id = B.id Y
  B.transfer_pair_id = A.id. Permite query partiendo de cualquier
  mitad sin JOIN extra.
- **Saldo por cuenta sólo en moneda nativa**. La query filtra
  `Transaction.currency == Account.currency` — txs en otra divisa
  dentro de una cuenta multi-divisa se ignoran de momento. Cuando
  haya tasa cross-currency aplicable (PHASE-19.5 hipotética),
  podemos sumar convirtiendo.
- **`mixed_currencies=true` en lugar de convertir automáticamente**.
  Si las cuentas activas no son monomoneda, los totales son suma
  cruda. La UI debe avisar al usuario que ese número no es
  comparable directamente. Auto-conversión requeriría definir una
  divisa de referencia y aplicar tasas — fase futura.
- **Filtro `account_id` en `/transactions`** se decidió aquí en
  lugar de en PHASE-21.2 porque el caso de uso aparece naturalmente
  con la BalancesCard (clic en una cuenta → ver sus tx).
- **Confirm dialog para "Deshacer" en mobile, no en web**. Mobile
  tiene más superficie para taps accidentales; web tiene click
  más preciso. Trade-off de UX.

## Limitaciones conocidas

- **Matcher no usa categoría como hint adicional**. Si el usuario
  marcara la salida como "Transferencias" y la entrada como
  "Bizum recibido", el matcher las consideraría candidatas igualmente
  por importe + cuentas. Aceptable; reduce falsos negativos.
- **Sin auto-detect en cron / al importar**. El matcher se dispara
  manualmente desde la pantalla de transferencias. Auto-detect en
  el cron requeriría semantica de "no notificar al usuario antes
  de revisar" — riesgo de emparejar mal sin supervisión.
- **No hay UI para `window_days` configurable**. La pantalla
  siempre usa `window_days=3`. Si llegan quejas, se añade selector.
- **Saldos no convierten cross-currency**. Si tienes cuenta EUR
  y broker USD, `total_assets` suma EUR + USD como si fueran la
  misma unidad. `mixed_currencies=true` lo señala pero no resuelve.
- **Sin filtro por cuenta en dashboard** (sólo en transactions).
  El dashboard agrega todas las cuentas. Filtrar el dashboard por
  cuenta requeriría propagar el param a 4 endpoints — follow-up
  si llega la petición.
- **Patrimonio neto no incluye liability** (todavía). PHASE-22
  añadirá cuentas tipo `credit_card`, `loan`, `mortgage` con
  `nature=liability` y `total_liabilities` empezará a sumar.

## Próxima fase

PHASE-22 — Módulo de deuda: tarjetas de crédito, préstamos,
hipotecas como cuentas tipo `liability`. Patrón de pago de cuota
(transfer principal + expense intereses). Métricas de debt-to-income
y time-to-payoff.
