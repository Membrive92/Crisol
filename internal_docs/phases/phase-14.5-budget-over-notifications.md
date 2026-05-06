# PHASE-14.5 — Notificaciones proactivas de budget over

**Estado**: ✅ completada
**Rama**: `feat/phase-14.5-budget-over-notifications`
**Fecha de merge**: 2026-05-06

## Objetivo

Hasta ahora el usuario sólo descubría que un presupuesto estaba en
warning/over abriendo `/budgets`. Esta fase añade notificación
proactiva: cuando crea una transacción, si la categoría afectada
(o el budget global) queda por encima de los umbrales, el toast
sale automáticamente. Sin push, sin polling — la respuesta del
POST trae la alert lista.

## Qué se implementó

### Backend

- **`budgets.service.get_alert_for_category(db, user_id, category_id)`**:
  itera candidatos (`category_id` → global) y devuelve el primer
  `BudgetStatusItem` cuyo status sea `warning` o `over`. `None` si
  no hay budget activo o si todos están en `ok`.
- **`transactions.schemas.BudgetAlertSchema`**: `{ budget_id,
  category_id, status, percent_used, spent_this_month, amount,
  currency, next_due_label }`. El `next_due_label` viene formateado
  por el backend ("Comida está al 85% del presupuesto.") para que
  el frontend solo lo lance al toast sin componer.
- **`TransactionResponse.budget_alert: BudgetAlertSchema | None`**.
  Sólo poblado en la respuesta del POST.
- **`transactions.router POST`**: tras crear (y antes del commit)
  llama a `get_alert_for_category`, busca el nombre de la
  categoría afectada (o "Presupuesto global" si `None`) y monta el
  `next_due_label`. Enriquece el payload con `model_copy`.

### Frontend

- **`packages/types/src/models/transaction.ts`**: nuevo tipo
  `BudgetAlert` exportado en `@finanzas/types`. `Transaction`
  añade `budget_alert?: BudgetAlert | null` opcional.
- **`packages/services/src/query/hooks/useTransactions.ts`**:
  `useCreateTransaction.onSuccess` ahora invalida también
  `budgets.all` (los status cards reflejan el nuevo estado al
  instante) y, si `created.budget_alert` viene poblado, dispara
  `toast.error` (status=over) o `toast.warning` (status=warning)
  con `next_due_label` directo. Sin lógica adicional en los
  callers — la notificación funciona en web, mobile y cualquier
  flujo que use el hook (manual, importer, receipt confirm).
- Nueva dep `@finanzas/store` en `packages/services` (necesaria
  para importar `toast` desde el hook).

### Tests

`backend/tests/test_transactions_budget_alerts.py` (6):

- Sin budget → `budget_alert: null`.
- Budget bajo umbral (<80%) → null.
- Warning (≥80%) → alert con porcentaje correcto + categoría +
  texto que incluye "85" y "Comida".
- Over (>100%) → alert con status='over'.
- Tx en categoría sin budget propio → dispara el global con
  texto "Presupuesto global".
- Categoría con budget OK + global en over → cae al global por
  iteración (decisión documentada).

Suite backend: **208/208** (+6 nuevos).

## Archivos clave

- `backend/app/modules/personal_finance/budgets/service.py`
  (`get_alert_for_category`)
- `backend/app/modules/personal_finance/transactions/schemas.py`
  (`BudgetAlertSchema` + campo en response)
- `backend/app/modules/personal_finance/transactions/router.py`
  (POST enriquece response con alert)
- `backend/tests/test_transactions_budget_alerts.py` (6 tests)
- `packages/types/src/models/transaction.ts` (`BudgetAlert`)
- `packages/types/src/index.ts` (re-export)
- `packages/services/src/query/hooks/useTransactions.ts`
  (toast + invalidate budgets)
- `packages/services/package.json` (`@finanzas/store` dep)

## Verificación

- [x] `pytest tests/` — 208/208.
- [x] `mypy app/` — 13 pre-existentes; 0 introducidos.
- [x] `ruff check app/ tests/` verde.
- [x] `pnpm lint` y `pnpm typecheck` verdes (workspaces todos).
- [x] `pnpm test` — 38 web + 5 mobile sin regresiones.
- [ ] Smoke manual:
  - [ ] Crear budget categoría EUR 100. Crear tx 85€ → toast
        warning bottom-right.
  - [ ] Crear tx adicional 50€ → toast error con 135%.
  - [ ] Crear budget global 50, categoría sin budget propio →
        tx 60€ → toast con texto "Presupuesto global".
  - [ ] Crear tx 10€ con cat OK → ningún toast.

## Decisiones tomadas

- **Backend devuelve label pre-formateado**. Compose en backend
  evita que cada frontend (web, mobile, futuras integraciones)
  duplique la lógica de "qué texto mostrar". El backend conoce el
  nombre de la categoría — el frontend sólo necesitaría hacer
  otra query para verlo.
- **Una sola alert por POST, no array**. La realidad común: una
  tx afecta a un solo budget (su categoría) y opcionalmente al
  global. Iterar y devolver el primero "interesante" reduce
  ruido. Si hay caso "tx muy grande dispara categoría Y global
  ambos", el usuario verá la categoría y al revisar `/budgets`
  verá el global también.
- **Categoría primero, global después**. Más específico antes que
  el catch-all. Si el de categoría está OK y el global en over,
  el usuario aún quiere saberlo (cae al global).
- **Toast.warning (warning) vs toast.error (over)**. Convención
  del sistema PHASE-11.3: warning auto-dismiss en 6s, error
  manual (forzar al usuario a leer). Coherente con la severidad
  semántica.
- **Hook invalida budgets.all en onSuccess**. Antes solo
  invalidaba `transactions.all`. Crear una tx afecta status de
  budgets — si el usuario ya está en `/budgets` o navega a la
  página justo después, el card refleja el cambio sin esperar
  staleTime.
- **`packages/services` gana dep en `packages/store`**. Era
  inevitable: el hook necesita disparar toasts y el toast vive
  en el store. La alternativa (mover toasts a `services`)
  rompería la separación conceptual (services es API client +
  hooks; store es state global UI).
- **Sin "umbral previo" check**. Una tx que mantiene el budget
  en warning (era 85, sigue 85) emite toast cada vez. Trade-off:
  ruido vs implementar memoria del estado anterior. Empezamos
  simple; si es ruidoso, añadir comparación estado-previo (BD)
  o rate-limit por categoría/día.

## Limitaciones conocidas

- **Sin cron de evaluación nocturno**. Cobertura real es POST
  /transactions. Si una tx se crea por API externa (importer
  síncrono ya lo cubre porque usa `create_transaction`) la
  notificación llega; si fuera async (futuras cargas en
  background) habría que añadir el hook ahí también.
- **Sin agrupación cross-currency**. El budget está en EUR; una
  tx en USD no dispara la alert (el `sum_expenses_in_period`
  filtra por currency). Coherente con PHASE-12.1 — "no
  cross-currency budgets". Si se prioriza, requiere cambio
  amplio en el módulo budgets.
- **El toast es la única superficie**. Sin push notification,
  sin email, sin badge en navegación. Si el usuario tiene la app
  cerrada, no se entera hasta que vuelve. Push/email es follow-up
  cuando exista canal.
- **Sin "agrupar tras N alerts seguidas"**. 5 tx en la misma
  categoría warning → 5 toasts. El sistema apila; podría ser
  ruidoso. Si pasa en uso real, dedup por `budget_id` en el
  store.

## Próxima fase

PHASE-14.6 — Cobertura UI mobile. Primer test smoke por
pantalla (analysis, transactions, trash, budgets, subscriptions),
reusando el setup de PHASE-11.6.
