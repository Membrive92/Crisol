# PHASE-3.1 — Dashboard backend

**Estado**: ✅ completada
**Rama**: `feat/phase-3.1-dashboard-backend`
**PR**: —
**Fecha de merge**: 2026-04-17

## Objetivo

Endpoints de agregación sobre `transactions` + `categories`: balance global,
desglose por categoría, evolución mensual y top de gastos. Módulo read-only
sin estado propio.

## Qué se implementó

- Nuevo módulo `backend/app/modules/dashboard/`:
  - `router.py` — `/dashboard/*` con 4 endpoints GET, todos con `CurrentUser`.
  - `service.py` — orquesta repositorio y devuelve Pydantic schemas.
  - `repository.py` — queries agregadas (SUM, COUNT, GROUP BY con joins a
    `categories`). Helper `_apply_scope[Q: Select[Any]](...)` que centraliza
    los filtros comunes (`user_id`, `currency`, rango de fechas).
  - `schemas.py` — sólo respuestas: `SummaryResponse`,
    `CategoryBreakdownItem`, `MonthlyBucket`, `TopExpenseItem`.
- Registrado en `backend/app/main.py` (`app.include_router(dashboard_router)`).
- **Moneda por defecto**: `USD` (configurable por query param `?currency=EUR`).
  Las transacciones guardan la moneda; el dashboard filtra por ella para
  evitar sumar importes en distintas divisas.

## Endpoints añadidos

| Método | Ruta | Query params | Response |
|--------|------|--------------|----------|
| GET | `/dashboard/summary` | `currency` (def `USD`), `date_from?`, `date_to?` | `{ income, expenses, balance, transaction_count, currency }` |
| GET | `/dashboard/by-category` | `currency`, `date_from?`, `date_to?`, `kind?` (`income\|expense`) | `[{ category_id, category_name, category_kind, total, count }]` |
| GET | `/dashboard/by-month` | `year` (def actual), `currency` | `[{ month: "YYYY-MM", income, expenses, balance }]` (12 buckets) |
| GET | `/dashboard/top-expenses` | `currency`, `date_from?`, `date_to?`, `limit` (1..50, def 10) | `[{ transaction_id, description, amount, occurred_at, category_id, category_name }]` |

### Reglas de agregación

- **`summary.transaction_count`**: cuenta todas las transacciones en el rango,
  incluidas las que no tienen categoría.
- **`summary.income` / `expenses`**: sólo transacciones con categoría (porque
  el signo lo define `category.kind`). Las sin categoría no cuentan para
  balance.
- **`by-category`**: incluye un bucket `{ category_id: null, category_name:
  "Sin categoría", category_kind: null }` con los totales de transacciones
  sin categoría. Ese bucket se **excluye** cuando se filtra por
  `?kind=income|expense` (no tiene kind).
- **`by-month`**: devuelve siempre 12 buckets (enero → diciembre) del año
  pedido, rellenando meses vacíos con 0.
- **`top-expenses`**: sólo transacciones cuya categoría es `expense`. Las
  sin categoría se excluyen: no se puede afirmar que sean gasto.

## Archivos clave

- `backend/app/modules/dashboard/router.py` — endpoints.
- `backend/app/modules/dashboard/service.py` — lógica de agregación.
- `backend/app/modules/dashboard/repository.py` — queries SQLAlchemy.
- `backend/app/modules/dashboard/schemas.py` — DTOs Pydantic.
- `backend/app/main.py` — registra el router.
- `backend/tests/test_dashboard.py` — 13 tests.

## Migraciones

Ninguna. El módulo es read-only sobre tablas existentes.

## Decisiones tomadas

- **USD como moneda por defecto**: a petición explícita del usuario. Las
  transacciones existentes en BD (default `EUR` según el schema) devolverán
  agregados en cero salvo que se pase `?currency=EUR`.
- **Importar `Transaction` y `Category` desde dashboard**: el principio de
  no importar entre módulos apunta a evitar acoplamiento de *lógica de
  negocio*. El dashboard es una vista SQL sobre esas tablas; importar los
  modelos ORM es inevitable sin duplicar definiciones. No se llama a
  `transactions.service` ni a `categories.service`.
- **Filtrado por `currency` obligatorio**: alternativa descartada —
  agregar por moneda y devolver un mapa. Para el MVP un usuario mira
  una moneda a la vez en su dashboard.
- **Helper genérico `_apply_scope[Q: Select[Any]]`**: sintaxis PEP 695
  (Python 3.12+). Evita anotaciones inferiores a `Any` cuando el helper
  se aplica sobre selects con tuplas heterogéneas.

## Verificación

- [x] `ruff check app/` verde.
- [x] `mypy app/` verde (strict, 42 archivos).
- [x] `pytest tests/test_dashboard.py` — 13/13 verde.
- [x] `pytest tests/` — 40/40 verde (suite completa).
- [x] Aislamiento multi-usuario verificado en los 4 endpoints.

## Limitaciones conocidas

- Sin agregación multi-moneda. Si un usuario opera en varias divisas
  tendrá que elegir cuál ver.
- Sin caché. Cada request reejecuta SUM/GROUP BY. Para volúmenes típicos
  de finanzas personales es trivial; si crece, se añadirá TTL cache.
- Sin índices nuevos. Las queries usan `(user_id, occurred_at, currency)` —
  si aparece regresión de performance se añadirá un índice compuesto en
  una migración.

## Próxima fase

PHASE-3.2 — Dashboard frontend (KPIs, gráfica de evolución, donut por
categoría en web + mobile).
