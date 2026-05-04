# PHASE-8.3 — Per-transaction conversion in SQL

**Estado**: ✅ completada
**Rama**: `feat/phase-8.2-currency-display` (acumula 8.2 + 8.3 — sin merge intermedio por petición del usuario, ver "Decisiones tomadas")
**PR**: —
**Fecha de merge**: 2026-05-03

## Objetivo

Cerrar la última aproximación que quedaba de PHASE-8.2: los agregados
del dashboard (Summary, by-month, by-category, top-expenses)
convertían cada moneda con **una sola tasa de fin de periodo** porque
los endpoints sumaban en SQL antes de aplicar la conversión. Una
transacción de febrero se convertía con la tasa de mayo, y los
totales fluctuaban con el spot de hoy en lugar de quedarse
clavados en la realidad histórica.

PHASE-8.3 mueve la conversión a SQL: cada transacción se multiplica
por la tasa **del día de su `occurred_at`** antes del `SUM`. Las
totales pasan a ser históricamente correctos y dejan de moverse al
día siguiente.

## Qué se implementó

### Backend — conversión per-tx en SQL

Helper nuevo
[`backend/app/modules/personal_finance/dashboard/conversion.py`](../../backend/app/modules/personal_finance/dashboard/conversion.py):

- `_latest_rate_subquery(quote, occurred_at)` — subquery escalar
  correlacionada que devuelve la última tasa EUR→`quote` ≤
  `occurred_at` dentro de la ventana de fallback de 14 días. NULL si
  no hay nada → la tx se excluye del SUM.
- `converted_amount_expr(target_currency)` — expresión SQL que
  devuelve el `Transaction.amount` convertido a `target_currency` con
  composición vía EUR:
  - `from == to` → amount.
  - `to == EUR` → `amount / from_rate`.
  - `from == EUR` → `amount * to_rate`.
  - resto → `amount * to_rate / from_rate`.
- `amount_is_convertible_expr(target_currency)` — boolean para
  contar las transacciones excluidas (`unconvertible_count`).

`PostgreSQL` admite `DATE - integer` para retroceder días, así
evitamos `INTERVAL` y los líos de auto-cast desde VARCHAR.

### Backend — `/dashboard/*` con `target_currency`

Los 4 endpoints aceptan ahora dos parámetros mutuamente excluyentes:

- `?currency=EUR` (legacy): filtra por esa moneda y agrega importes
  crudos. Comportamiento pre-PHASE-8.3.
- `?target_currency=EUR` (nuevo): no filtra. Convierte cada
  transacción al destino con la tasa del día de su `occurred_at` y
  agrega después.

Si llegan ambos, gana `target_currency`. Si no llega ninguno,
default a `currency=USD` (legacy) para no romper consumidores
externos.

`SummaryResponse` añade `unconvertible_count: int` — número de
transacciones del rango que el SQL no pudo convertir por falta de
tasa (NULL del subquery). Sólo > 0 en modo cross-currency.

### Backend — backfill on-demand de fechas históricas

Cuando un usuario tiene transacciones más antiguas que el snapshot
embebido (sólo cubre 6 anchors entre 2024-01-02 y 2026-04-01) y
fuera de la ventana de 14 días, el SQL devuelve NULL para esas
filas y el SUM queda corto.

`currency.service.ensure_rates_for_dates(dates)` es el nuevo helper
que:

1. Para cada fecha pedida, comprueba si hay tasa exacta o reciente
   en BD (vía `get_rate_with_fallback`).
2. Si no, llama a frankfurter para esa fecha y persiste el set
   canónico (`COMMON_QUOTES = USD GBP JPY CHF CAD AUD MXN BRL CNY`).
3. Best-effort: errores de red por fecha se tragan.

`dashboard.service._ensure_rates_in_scope` lo invoca antes de
agregar en cualquier endpoint cross-currency:

1. `SELECT DISTINCT cast(occurred_at, DATE) FROM transactions
   WHERE user_id = ? AND currency != target [AND date filters]`.
2. `ensure_rates_for_dates(dates)`.

Tras el primer hit a una fecha la tasa queda en BD para siempre.

### Frontend — simplificación

PHASE-8.2 había introducido `apps/web/lib/cross-currency.ts` con
helpers `aggregateSummaries / aggregateMonthly / aggregateByCategory`
para sumar slices por moneda en cliente. PHASE-8.3 los borra: ahora
una **única** llamada por endpoint con `?target_currency=` cubre el
caso. El cliente queda más simple:

- `apps/web/lib/cross-currency.ts` → eliminado.
- `useDashboard.ts`: eliminado el flag `enabled` que apagaba los
  hooks single-currency (ya no se necesita, hay un solo hook por
  pantalla).
- `dashboard/page.tsx`, `personal-finance/analysis/page.tsx`,
  `stitch-transactions-kpi-row.tsx`: una sola query por endpoint.
  Cuando `convertAll === true` mandan `target_currency`; si no,
  `currency` legacy.
- Banner amarillo "⚠ X transacciones sin tasa disponible" en
  Dashboard y Análisis cuando `summary.unconvertible_count > 0`.

### Frontend — selector de periodo unificado

Como parte de la simplificación, el Dashboard cambia su `YearSelect`
por el mismo `StitchPeriodToggle` (Mes / Trimestre / Año) que ya
usaba Analysis. Razón: ambas vistas comparten la misma forma del
endpoint summary (`date_from`/`date_to` + `target_currency`), así que
no hay motivo para que el selector difiera. La chart de balance
sigue usando el año actual completo (igual que Analysis), aunque los
KPIs y el desglose por categoría se filtran al periodo seleccionado.

- `apps/web/app/(app)/dashboard/page.tsx` reusa
  `StitchPeriodToggle` + `rangeForPeriod` de
  `components/analysis/stitch-period-toggle.tsx`.
- `apps/web/components/dashboard/year-select.tsx` → eliminado.

### Frontend — fix visual: salto de línea bajo el importe

`stitch-key-metrics.tsx` (cards "Flujo de caja neto" y "Tasa de
ahorro") tenía el `<span>` del importe en flujo inline; cuando el
caption inferior usaba `display: inline-block` con `marginTop`, ambos
caían en la misma línea (margin-top entre inlines no separa
visualmente). Añadido `display: 'block'` al span del importe en
ambas cards para forzar la separación.

La tabla de transacciones (`transaction-list.tsx`) **mantiene** el
patrón per-row de PHASE-8.2 (`useQueries` por fecha distinta) — la
columna `≈` muted necesita la fecha de cada fila y eso ya funcionaba
antes. No se simplifica en esta fase porque el endpoint
`/transactions` no devuelve el converted amount; portarlo es un
follow-up.

### Tipos compartidos

- `DashboardSummaryQuery / ByCategory / ByMonth / TopExpensesQuery`
  añaden `target_currency?: string`.
- `DashboardSummary` añade `unconvertible_count: number`.

## Flujo técnico

```
 Frontend (Dashboard, Analysis, KPIs Transactions)
    │
    │ GET /dashboard/summary?target_currency=USD&date_from=&date_to=
    ▼
 Service: _ensure_rates_in_scope
    ├── SELECT DISTINCT cast(occurred_at, DATE)
    │     FROM transactions
    │     WHERE user_id=? AND currency != target [AND scope]
    ├── for each date: ensure_rates_for_dates(date)
    │     ├── get_rate_with_fallback(date) → existe? skip
    │     └── refresh_rates(date) → frankfurter.dev/v1/{date}
    │           └── upsert_rates(date, USD/GBP/JPY/...)
    ▼
 Repository: SUM(converted_amount_expr(target))
    converted_amount_expr usa subqueries correlacionadas:
        SELECT rate FROM exchange_rates
         WHERE base='EUR' AND quote=tx.currency
           AND rate_date <= tx.occurred_at::date
           AND rate_date >= tx.occurred_at::date - 14
         ORDER BY rate_date DESC LIMIT 1
    NULL → tx excluida del SUM, contada en unconvertible_count
    ▼
 Frontend renderiza KPIs en moneda destino + banner si hay missing
```

## Archivos clave

- `backend/app/modules/personal_finance/dashboard/conversion.py` (nuevo)
- `backend/app/modules/personal_finance/dashboard/repository.py`
- `backend/app/modules/personal_finance/dashboard/service.py`
- `backend/app/modules/personal_finance/dashboard/router.py`
- `backend/app/modules/personal_finance/dashboard/schemas.py`
- `backend/app/modules/currency/service.py` (`COMMON_QUOTES`,
  `ensure_rates_for_dates`)
- `backend/app/modules/currency/router.py` (consume `COMMON_QUOTES`)
- `backend/tests/test_dashboard_cross_currency.py` (nuevo, 9 tests)
- `packages/types/src/dto/dashboard.dto.ts` (target_currency)
- `packages/types/src/models/dashboard.ts` (unconvertible_count)
- `packages/services/src/query/hooks/useDashboard.ts`
- `apps/web/app/(app)/dashboard/page.tsx` (period toggle unificado +
  simplificación a una sola query)
- `apps/web/app/(app)/personal-finance/analysis/page.tsx`
- `apps/web/components/transactions/stitch-transactions-kpi-row.tsx`
- `apps/web/components/analysis/stitch-key-metrics.tsx` (fix
  `display: block` bajo el importe)
- ~~`apps/web/lib/cross-currency.ts`~~ (eliminado)
- ~~`apps/web/components/dashboard/year-select.tsx`~~ (eliminado)

## Endpoints modificados

Mismos 4 endpoints `/dashboard/*` pero con un nuevo modo:

| Método | Ruta | Query nueva | Notas |
|--------|------|------------|-------|
| GET | `/dashboard/summary` | `?target_currency=` | conversión per-tx + `unconvertible_count` en respuesta |
| GET | `/dashboard/by-month` | `?target_currency=` | totales mensuales convertidos per-tx |
| GET | `/dashboard/by-category` | `?target_currency=` | totales por categoría convertidos per-tx |
| GET | `/dashboard/top-expenses` | `?target_currency=` | ordenación por importe convertido desc |

Los modos `?currency=` legacy y los demás parámetros (date_from,
date_to, kind, year, limit) son compatibles 1:1 con PHASE-3.1.

## Migraciones

Ninguna. PHASE-8.1 ya creó `exchange_rates`; aquí sólo añadimos
queries que la usan.

## Verificación

- [x] `pytest backend/tests/` — 158/158 (9 nuevos en
      `test_dashboard_cross_currency.py`).
- [x] `ruff check` backend verde.
- [x] `pnpm typecheck`, `pnpm lint`, `pnpm test` (frontend) verdes.
- [x] Smoke real con datos de usuario:
  - Tx 27,66 € del 19-feb-2026 + Tx 2 USD del 03-may-2026, target USD.
  - Backend dispara lazy fetch para 19-feb → frankfurter responde
    `EUR/USD = 1.1753` (rate ECB oficial del 19-feb-2026), persiste.
  - Total: 27,66 × 1.1753 + 2 = 34,51 USD.
  - El total se mantiene estable al recargar al día siguiente —
    deja de fluctuar con el spot.
  - Verificación adicional vs el "otro AI" que afirmaba 1,1773: la
    diferencia ~0.17 % viene de usar fixings comerciales
    (Reuters/Bloomberg/Oanda) en lugar del fixing ECB que sirve
    frankfurter. El proyecto se alinea con ECB por principio
    (datos públicos anónimos, sin API key, sin tracking).

## Decisiones tomadas

- **JOIN en SQL vs agregación cliente**. El frontend de PHASE-8.2
  pedía N veces (una por moneda) y combinaba en JS. Funcionaba pero
  era N round-trips y la tasa era única por periodo. La opción del
  JOIN en SQL es ortogonal: cada fila se convierte con su rate, el
  agregado se hace en BD (rápido, indexado), y el frontend recibe
  un único objeto.
- **Subqueries correlacionadas vs LATERAL JOIN**. SQLAlchemy soporta
  ambos. Las correlacionadas son más portables y tienen
  prácticamente el mismo plan en PostgreSQL para tablas pequeñas.
  Si `exchange_rates` crece a millones de filas habría que medir.
- **Ventana de fallback en SQL = misma 14 días que repo**. Mantener
  el invariante "una sola política de fallback" — tanto el `convert`
  síncrono del módulo `currency` como el SQL JOIN del dashboard
  usan los mismos 14 días.
- **`PostgreSQL DATE - integer` en lugar de `INTERVAL`**. Reduce
  cast issues y produce SQL más limpio. SQLAlchemy lo traduce
  literal.
- **Lazy fetch por fecha de transacción al entrar al endpoint**. Sin
  esto, transacciones históricas más antiguas que el snapshot +
  ventana quedaban como `unconvertible`. El usuario nunca vería su
  total real. Con esto, el primer request por fecha trae la tasa y
  queda persistida.
- **`COMMON_QUOTES` movido de router → service**. Sirve a varios
  callers (lazy fetch del endpoint y backfill on-scope del
  dashboard). Mantenerlo en `currency.service` es el sitio
  natural; el router lo importa.
- **Branch única acumula 8.2 + 8.3**. El usuario pidió no hacer
  commits intermedios para evitar churn (8.3 modifica heavy lo de
  8.2: borra `cross-currency.ts`, simplifica páginas, cambia
  contratos). Cuando se haga el commit run, los grupos lógicos se
  pueden separar en commits secuenciales (foundations 8.2 →
  display 8.2 → SQL conversion 8.3 → dashboard simplification
  8.3 → docs).
- **Contar `unconvertible_count` con expresión SQL separada**.
  El SUM ya excluye NULL pero no expone el conteo. Una segunda
  query con `COUNT(*) WHERE NOT amount_is_convertible_expr` es
  trivial y permite al frontend mostrar "X transacciones sin tasa".
  Sólo se ejecuta en modo cross-currency.
- **Mantener legacy `currency` filter**. El toggle "Convertir todas
  las monedas" del header puede estar OFF — eso pinta sólo los
  importes en la moneda activa, sin conversión. El backend cubre
  ambos modos sin breaking changes en consumidores externos.

## Limitaciones conocidas

- **Tabla `transactions` no incluye `converted_amount`**. La
  tabla de transacciones sigue usando `useQueries` por fecha distinta
  desde el frontend (PHASE-8.2). Portarlo al backend (que devuelva
  `?target_currency=` con un campo `converted_amount` por fila) es
  follow-up.
- **`COUNT(*)` de unconvertible vuelve a recorrer el scope**. Hay
  una query extra en cada llamada cross-currency a `summary`. En
  un usuario con 100k transacciones podría notarse. Si pasa,
  hacerlo subquery en el mismo SELECT es trivial.
- **`top-expenses` ordena por convertido pero la respuesta usa el
  campo `amount`**. El consumidor no sabe si está viendo el
  convertido o el original. Aceptable para MVP — el convertido es
  lo que tiene sentido en el contexto del dashboard. Si el frontend
  necesita ambos, añadimos `original_amount` + `original_currency`
  a la respuesta.
- **`ensure_rates_for_dates` hace una llamada por fecha**. Para un
  usuario con 50 fechas distintas es 50 round-trips a frankfurter
  la primera vez. Una vez en caché, 0. Frankfurter no soporta batch
  por múltiples fechas en una sola request, así que la única
  optimización sería paralelizar (`asyncio.gather`). Lo dejamos
  serial por simpleza — la primera carga puede tardar segundos
  pero las siguientes son instantáneas.
- **Snapshot embebido tiene tasas aproximadas**. Las upserts del
  lazy fetch las sobreescriben con datos reales de frankfurter, así
  que las aproximaciones sólo afectan al primer arranque sin red.
- **JPY redondeo a 2 decimales**. JPY usa 0 decimales en producción
  real. Por ahora no hemos visto datos JPY; cuando lleguen, la
  política de quantize por moneda iría en `currency.service`.
- **Sin cron nocturno explícito**. El lazy fetch lo cubre "al
  primer request del día". Suficiente mientras el usuario abra la
  app de vez en cuando. Si se quiere proactivo, añadir
  APScheduler/cron en docker-compose.

## Próxima fase

Sin definir formalmente. Candidatos siguientes (no priorizados):

- `/transactions` con `?target_currency=` para que la tabla deje
  el patrón `useQueries` por fecha.
- Cron nocturno explícito (APScheduler) para refrescar las tasas de
  ayer sin esperar al primer usuario activo.
- Detección de subscripciones recurrentes vía AI (módulo `ai`).
- Modelo de presupuestos por categoría con alertas.
- Selector de icono y color al crear categoría.
- Drawer mobile para la sidebar.
