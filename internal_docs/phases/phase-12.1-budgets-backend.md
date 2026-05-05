# PHASE-12.1 — Backend de presupuestos mensuales

**Estado**: ✅ completada
**Rama**: `feat/phase-12.1-budgets-backend`
**Fecha de merge**: 2026-05-05

## Objetivo

Primera feature analítica de la app que va más allá del dashboard
read-only: el usuario define límites mensuales de gasto por
categoría (o globales) y el backend calcula spent vs budget con
estado `ok | warning | over`. Esta fase entrega el **backend
completo** (modelo + endpoints + status + tests). PHASE-12.2 / 12.3
añaden el frontend (web / mobile).

## Qué se implementó

### Modelo `Budget` (`backend/app/modules/personal_finance/budgets/models.py`)

```
budgets:
  id              UUID PK
  user_id         UUID NOT NULL → users.id (CASCADE)
  category_id     UUID NULL     → categories.id (SET NULL)
  amount          NUMERIC(14,2)
  currency        CHAR(3) DEFAULT 'EUR'
  effective_from  DATE
  effective_to    DATE NULL  (NULL = vigente)
  created_at, updated_at TIMESTAMPTZ
```

- `category_id IS NULL` → presupuesto **global** del mes (suma todas
  las categorías de gasto del usuario).
- `effective_from` / `effective_to` permiten cerrar y crear nuevos
  sin perder histórico.
- Índices: `ix_budgets_user_id`, `ix_budgets_category_id`.

### Migración `f8b3c91d4e22`

Crea `budgets` + 2 índices. `downgrade()` simétrico. Aplicada a la
DB local.

### Repository

- `list_active_budgets(user_id, today)` — `effective_to IS NULL OR
  >= today`.
- `get_budget_by_id(budget_id, user_id)` — scoped al user.
- `get_active_budget_for_category(user_id, category_id, today)` —
  detecta duplicado para el conflict 409.
- `create_budget(budget)`, `delete_budget(budget)` — primitives.
- **`sum_expenses_in_period`** — el query interesante: suma de
  transacciones activas (excluye soft-deleted PHASE-10.1) en el
  rango de fechas, kind='expense', misma currency. Filtra por
  categoría opcional (`None` = todas).

### Service

- **Política "uno activo por (user, category)"** vía 409 en create.
  Para reemplazar: DELETE el actual y crear nuevo.
- **`update_budget`** sólo permite `amount` y `currency`.
  `effective_from` y `category_id` son inmutables — para cambiarlos
  hay que cerrar y crear nuevo (preserva histórico real).
- **`close_budget`** (DELETE endpoint): si `effective_to IS NULL` o
  futuro, lo pone a `today`. Si ya estaba cerrado en el pasado,
  hace DELETE real para limpiar (idempotente).
- **`get_budgets_status`**: por cada budget activo, calcula `spent`
  con `sum_expenses_in_period`, `remaining = amount - spent`,
  `percent_used = spent/amount * 100`, status según umbrales:
  - `< 80%` → ok
  - `80-100%` → warning
  - `> 100%` → over
- **`_today_utc()` y `_month_bounds_utc(today)`**: cálculos
  deterministas en UTC. `month_end` es último-día 23:59:59.999999+00.
  Coherente con el cron de PHASE-11.1.

### Endpoints

| Método | Ruta | Body / Query | Response |
|--------|------|--------------|----------|
| GET | `/budgets` | — | `200 BudgetResponse[]` (activos) |
| GET | `/budgets/status` | — | `200 BudgetStatusResponse` |
| GET | `/budgets/{id}` | — | `200 BudgetResponse` |
| POST | `/budgets` | `{ category_id?, amount, currency, effective_from }` | `201 BudgetResponse`, `409` si duplicado activo |
| PUT | `/budgets/{id}` | `{ amount?, currency? }` | `200 BudgetResponse` |
| DELETE | `/budgets/{id}` | — | `204` (cierra `effective_to=today` o DELETE real si ya estaba cerrado) |

### Wiring

- `app/main.py` registra `budgets_router`.
- `tests/conftest.py` importa `Budget` para que `Base.metadata` lo
  conozca al crear la BD de tests.

### Tests `test_budgets.py` (10)

- Create + list happy path.
- 409 al crear duplicado activo.
- Global budget (`category_id=null`) coexiste con el de categoría.
- Update amount + currency.
- Delete cierra `effective_to=today`.
- Aislamiento user A/B.
- Status sin transacciones → ok / 0 / 0%.
- Status warning (90%) y over (140%).
- Status global suma todas las categorías de gasto.
- Status excluye soft-deleted (regresión cruzada con PHASE-10.1).

Suite completo: **188/188** (10 nuevos sobre 178 previos).

## Flujo técnico

```
 GET /budgets/status
    ▼
 service.get_budgets_status(db, user_id)
    ├── today = _today_utc()
    ├── (month_start, month_end) = _month_bounds_utc(today)
    ├── budgets = list_active_budgets(db, user_id, today=today)
    └── for budget in budgets:
            spent = sum_expenses_in_period(
              db, user_id,
              currency=budget.currency,
              month_start=month_start,
              month_end=month_end,
              category_id=budget.category_id,
            )
            percent_used = spent / amount * 100
            status = 'over' if >100 else 'warning' if >=80 else 'ok'
            items.append(BudgetStatusItem(...))
    ▼
 BudgetStatusResponse(items, month_start, month_end)
```

## Archivos clave

- `backend/alembic/versions/f8b3c91d4e22_budgets_module.py` (nuevo)
- `backend/app/modules/personal_finance/budgets/__init__.py`
- `backend/app/modules/personal_finance/budgets/models.py`
- `backend/app/modules/personal_finance/budgets/schemas.py`
- `backend/app/modules/personal_finance/budgets/repository.py`
  (CRUD + `sum_expenses_in_period`)
- `backend/app/modules/personal_finance/budgets/service.py`
  (políticas + status calc)
- `backend/app/modules/personal_finance/budgets/router.py`
- `backend/app/main.py` (router incluido)
- `backend/tests/conftest.py` (Budget importado)
- `backend/tests/test_budgets.py` (10 tests)

## Verificación

- [x] `pytest tests/` — 188/188.
- [x] `mypy app/` — 13 pre-existentes (`ai/client.py`,
      `dashboard/conversion.py`); **0 introducidos**.
- [x] `ruff check app/ tests/` verde.
- [ ] Smoke manual con DB real:
  - [ ] Crear budget (con / sin categoría).
  - [ ] Crear duplicado → 409.
  - [ ] Insertar transacciones → status refleja spent y % correcto.
  - [ ] DELETE inicial → effective_to=today; DELETE de nuevo → 204
        no cambia (mantiene cerrado).

## Decisiones tomadas

- **Política "uno activo por (user, category)" en service, no en
  unique constraint a nivel BD**. La constraint sería
  `UNIQUE(user_id, category_id) WHERE effective_to IS NULL` —
  estricta. Pero futuros casos de "presupuestos parciales"
  (vacaciones que dura 2 semanas, cierre temporal de gastos en una
  categoría) podrían requerir overlap. Service-level es flexible.
- **`effective_from`/`category_id` inmutables tras crear**.
  Cambiarlos rompería el histórico (¿qué presupuesto regía en
  qué momento?). Cerrar y crear nuevo es la fricción esperada.
- **`close_budget` con DELETE real cuando ya estaba cerrado en el
  pasado**. Idempotencia desde el lado del usuario: dos DELETEs
  consecutivos no fallan, el segundo limpia. Reduce ruido en BD
  para casos "creé por error y borré inmediatamente".
- **No multi-currency en presupuestos**. El budget vive en una
  currency fija; spent se compara 1:1. Cross-currency budget
  (toggle convertAll aplicable) requiere decisión adicional sobre
  qué tasa usar y cuándo. Backlog cuando llegue el caso.
- **Status calculado en cada GET, sin cache**. Para volúmenes
  esperados (< 20 budgets activos por usuario, queries de ~ms cada
  una) no compensa el overhead de TTL cache + invalidation. Si se
  vuelve hot path, mover a cache con invalidation por tx insertada.
- **`sum_expenses_in_period` excluye soft-deleted**. Consistente
  con PHASE-10.1: una tx en papelera no contribuye al spent.
- **UTC para `today` y month bounds**. Mismo razonamiento que el
  cron de tasas (PHASE-11.1) — el límite de mes calendario debe
  ser determinista independientemente del TZ del servidor.
- **Tests usan `date.today()` (TZ local) para insertar txs**. Es
  el formato que la API acepta y los tests no necesitan ser
  estrictos UTC — el desfase < 24h no afecta a las assertions
  porque las txs caen claramente dentro del mes.

## Limitaciones conocidas

- **Sin alertas push/email**. Status warning/over sólo se observa
  al hacer `GET /budgets/status`. Notificaciones proactivas
  (cuando una tx insertada empuja una categoría a `over`) son
  follow-up — requiere event hook en `transactions.service.create`
  + canal de notificación.
- **Sin cron nocturno de evaluación**. Mismo razonamiento — sin
  notificaciones push no hace falta.
- **Sólo periodo mensual**. Semanal/anual/personalizado pendiente.
  El campo `effective_from`/`effective_to` permitiría representar
  rangos arbitrarios, pero la lógica de status asume mes calendario.
- **Sin cross-currency**. Decidido (ver decisiones).
- **`get_budgets_status` hace N queries** (una por budget). Para
  los volúmenes esperados es ~ms y la lectura es trivial. Si
  llega un usuario con 100+ budgets activos, consolidar a 1 query
  con GROUP BY.
- **Sin endpoint de "histórico"** (`GET /budgets/history?year=`
  para ver los budgets cerrados). Datos están — falta exponerlos
  cuando alguna pantalla lo pida.

## Próxima fase

PHASE-12.2 — Frontend web. Ruta `/personal-finance/budgets` con:
- Lista de budgets activos + form de crear nuevo.
- Tarjeta `BudgetStatusCard` por cada budget activo (barra de
  progreso, status color).
- Tarjeta agregada en el dashboard "Estado de presupuestos" como
  preview.
- Hooks `useBudgets`, `useBudgetStatus`, `useCreateBudget`,
  `useUpdateBudget`, `useDeleteBudget` en `packages/services`.
