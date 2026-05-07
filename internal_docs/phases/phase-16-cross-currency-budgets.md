# PHASE-16 — Cross-currency budgets (opt-in flag)

**Estado**: ✅ completada
**Rama**: `feat/phase-16-cross-currency-budgets`
**Fecha de merge**: 2026-05-06

## Objetivo

Heredado del backlog: hasta ahora un budget en EUR sólo veía las
transacciones marcadas como EUR. Un usuario que paga Netflix en
USD, mete gastos de viaje en GBP y carga la mayoría en EUR no
tenía forma de que el budget de "Suscripciones" o "Viajes"
contara los gastos en otras monedas. La opción cero (convertir
siempre) tampoco vale: el usuario por defecto ve su moneda
local y no quiere que tasas variables muevan el `spent` mes a
mes en categorías 100% locales.

Solución: opt-in por budget vía flag `convert_other_currencies`.
Off por defecto (compat 100% con pre-PHASE-16); on cuando el
usuario lo activa explícitamente.

## Qué se implementó

### Backend

- **Migración `c54e9b3a7d18`**: añade
  `budgets.convert_other_currencies BOOLEAN NOT NULL DEFAULT FALSE`.
  `server_default=sa.false()` para que filas existentes queden en
  `false` sin necesidad de backfill manual. Downgrade limpio
  (`drop_column`).
- **Modelo `Budget`**: nuevo campo `convert_other_currencies:
  Mapped[bool]` con `server_default="false"`.
- **Schemas Pydantic**:
  - `BudgetCreate.convert_other_currencies: bool = False`
  - `BudgetUpdate.convert_other_currencies: bool | None = None`
    (toggle vía PUT)
  - `BudgetResponse.convert_other_currencies: bool`
  - `BudgetStatusItem.unconvertible_count: int = 0` — nuevo campo
    de respuesta para reportar cuántas txs cayeron fuera del
    SUM por falta de tasa.
- **Repository `sum_expenses_in_period`**: ahora devuelve
  `tuple[Decimal, int]` (total, unconvertible_count) y acepta
  `convert_other_currencies: bool = False`.
  - Off → comportamiento legacy: filtra
    `Transaction.currency == budget.currency`. `unconvertible_count = 0`.
  - On → reusa los helpers SQL de PHASE-8.3 (`converted_amount_expr`,
    `amount_is_convertible_expr`). El SUM convierte cada tx a la
    moneda del budget con la tasa del día de la tx; las txs sin
    tasa disponible quedan fuera (NULL → SUM ignora) y se cuentan
    en `unconvertible_count` con un `COUNT(*) WHERE NOT convertible`.
- **Service**:
  - `create_budget` propaga el flag al modelo.
  - `get_budgets_status`: para cada moneda única de un budget con
    flag on, llama a `ensure_rates_for_user_scope` antes de las
    SUMs — backfill upfront para evitar lazy-fetch storms durante
    la query.
  - `get_alert_for_category` (PHASE-14.5): si el budget candidato
    tiene flag on, también backfillea tasas antes de calcular y
    propaga `unconvertible_count` al alert.

### Frontend (capa shared)

- `Budget.convert_other_currencies: boolean` en `@finanzas/types`.
- `BudgetStatusItem.unconvertible_count: number`.
- DTOs: `BudgetCreateRequest.convert_other_currencies?: boolean` y
  `BudgetUpdateRequest.convert_other_currencies?: boolean`.

### Web (`/personal-finance/budgets`)

- `BudgetForm`: nuevo checkbox "Sumar transacciones en otras
  monedas" + hint con la moneda del budget. Off por defecto.
- `BudgetStatusCard`: cuando `unconvertible_count > 0`, debajo
  del footer aparece "≈ N transacciones sin tasa" con
  `colors.warning` y `title` explicativo.

### Mobile (`/personal-finance/budgets`)

- `BudgetFormModal`: equivalente nativo del checkbox — `Pressable`
  con cuadrado custom + check ASCII (no react-native-checkbox para
  no añadir dep). Mismo hint debajo.
- `BudgetStatusCard`: chip `unconvertible` con `colors.warning`
  cuando > 0.

### Tests

`backend/tests/test_budgets_cross_currency.py` (6 tests):

- `test_create_budget_with_cross_currency_flag` — flag se persiste
  y default sigue siendo `false`.
- `test_status_without_flag_ignores_other_currencies` — sin flag,
  una tx en USD no cuenta para un budget EUR.
- `test_status_with_flag_sums_converted` — con flag y tasa
  EUR→USD seedeada, 50 USD ≈ 45.45 EUR aparece en `spent`.
- `test_status_with_flag_reports_unconvertible` — tx en `XYZ`
  (sin tasa) queda fuera del SUM y suma 1 a `unconvertible_count`.
- `test_update_can_toggle_flag` — PUT activa/desactiva.
- `test_alert_respects_flag` — el alert proactivo de PHASE-14.5
  honra el flag (warning con tx en USD).

Helper privado `_seed_rate` inserta `ExchangeRate` directamente
en BD para que los tests no dependan de frankfurter.

Suite backend: **231/231** (+6 nuevos sobre 225).
Frontend: 40 web + 18 mobile sin regresiones (test fixtures
actualizados con los dos campos nuevos requeridos).

## Archivos clave

- `backend/alembic/versions/c54e9b3a7d18_budgets_cross_currency_flag.py` (nuevo)
- `backend/app/modules/personal_finance/budgets/models.py`
- `backend/app/modules/personal_finance/budgets/schemas.py`
- `backend/app/modules/personal_finance/budgets/repository.py` (`sum_expenses_in_period` reescrito)
- `backend/app/modules/personal_finance/budgets/service.py` (3 funciones tocadas)
- `backend/tests/test_budgets_cross_currency.py` (6 tests)
- `packages/types/src/models/budget.ts`
- `packages/types/src/dto/budget.dto.ts`
- `apps/web/components/budgets/budget-form.tsx` (checkbox)
- `apps/web/components/budgets/budget-status-card.tsx` (chip unconvertible)
- `apps/mobile/components/budgets/budget-form-modal.tsx` (toggle nativo)
- `apps/mobile/components/budgets/budget-status-card.tsx` (chip unconvertible)

## Verificación

- [x] `pnpm typecheck` y `pnpm lint` verdes.
- [x] `pytest tests/` — 231/231.
- [x] `pnpm test` — 40 web + 18 mobile sin regresiones.
- [ ] Smoke:
  - [ ] Crear budget EUR sin flag → tx USD no cuenta.
  - [ ] Activar flag en ese budget vía PUT → tx USD aparece
        convertida en `spent`.
  - [ ] Crear tx en moneda exótica sin tasa → chip "≈ N
        transacciones sin tasa" en la card.
  - [ ] Crear tx que dispare warning con flag on → toast del
        alert llega.

## Decisiones tomadas

- **Opt-in por budget, no global**. Un toggle global "convertir
  todo" mueve el `spent` de budgets 100% locales por culpa de
  oscilaciones de tasa, lo que el usuario no espera. El opt-in
  por budget hace explícita la intención: "este budget mezcla
  monedas, conviértelas".
- **Tasa del día de cada tx, no del día del cálculo**. Coherencia
  con PHASE-8.3 (per-tx conversion en dashboard). Si el usuario
  gasta 50 USD el día 1 y 50 USD el día 30, y la tasa cambia,
  cada gasto se convierte con su propia tasa — el `spent` no se
  reescribe retroactivamente cuando la tasa de hoy cambia.
- **`unconvertible_count` reportado, no oculto**. Si una tx queda
  fuera del SUM por falta de tasa, el usuario debe verlo (chip
  warning). Esconder ese conteo daría una sensación falsa de
  "estoy bien de presupuesto" cuando en realidad falta info.
- **Backfill upfront vía `ensure_rates_for_user_scope`**. Sin
  esto, cada SUM lazy-fetchea tasas faltantes en serie. Al
  precalcular el set de monedas únicas y backfillear una vez
  por moneda, una página de status con N budgets → max N
  llamadas a frankfurter en lugar de potenciales N×M.
- **Reusar helpers de PHASE-8.3** (`converted_amount_expr`,
  `amount_is_convertible_expr`). No reinventar la subquery
  correlacionada — ya está testeada en dashboard.
- **PUT permite toggle**. El usuario puede activar/desactivar el
  flag sin tener que cerrar el budget y crear uno nuevo. Cambio
  no destructivo: sólo afecta a las queries de status futuras.

## Limitaciones conocidas

- **Sin tests UI** del checkbox/toggle web/mobile. Los componentes
  visuales (form + status card) son cambios visuales
  incrementales, los handlers son el mismo patrón mutation+toast
  que ya estaba.
- **`ensure_rates_for_user_scope` puede tardar** si el usuario
  tiene muchas monedas exóticas. Para los volúmenes esperados
  (< 5 monedas distintas por usuario) el coste es despreciable;
  si emerge, mover a job en background.
- **Sin filtro "sólo budgets con flag on"** en el listado.
  Mezcla deliberadamente budgets convertidos y no convertidos
  en la misma página — el chip `unconvertible` distingue.

## Cierre PHASE-16

Cierra el último deferred del backlog que dependía de decisión
de diseño. Los demás (Ollama detector, E2E mobile,
push/email) siguen pendientes con motivos previos.
