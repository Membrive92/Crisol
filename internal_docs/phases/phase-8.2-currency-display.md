# PHASE-8.2 — Currency conversion frontend

**Estado**: ✅ completada
**Rama**: `feat/phase-8.2-currency-display` (rebased onto 8.1)
**PR**: —
**Fecha de merge**: 2026-05-03

## Objetivo

Cerrar el círculo abierto en PHASE-8.1: las tasas ya están en BD,
ahora las pantallas que filtraban por una sola moneda activa pasan a
**sumar cross-currency** convirtiendo cada transacción a la moneda
del header. El usuario ve "su patrimonio" como un único número en
lugar de N totales separados por moneda.

## Qué se implementó

### Backend — lazy fetch on-demand

PHASE-8.1 dejó el snapshot embebido y el cliente HTTP, pero el
trigger lazy quedaba pendiente. Sin él, `/currency/rates?date=hoy`
devolvía lista vacía hasta que alguien manualmente disparase
`refresh_rates`.

- `currency/router._maybe_lazy_fetch` cubre el path `/rates` y
  `/convert`: si la BD no tiene la fecha pedida y la fecha está
  dentro del horizonte (±400 días, sólo pasado), llama a frankfurter
  con un set canónico (`USD GBP JPY CHF CAD AUD MXN BRL CNY`),
  persiste y reconsulta.
- Best-effort: si frankfurter está caído, swallow → endpoint sigue
  funcionando con lo que haya en BD.
- Fechas futuras se ignoran (frankfurter las devuelve como "latest"
  y persistirlas contaminaría el bucket de la fecha pedida).
- Tests: `lazy_fetches_unknown_date`, `skips_lazy_fetch_for_old_dates`,
  `swallow_when_frankfurter_down`. El test `convert_returns_missing`
  se reescribió para mockear el cliente y no depender de red.

### Shared utilities (`packages/`)

- `packages/ui/src/format.ts`:
  - `RatesMap` (typed alias) + `convertAmount(amount, from, to, rates)`
    devolviendo `{ value, rate, missing }`. Composición vía EUR
    cuando ninguna pata es EUR.
  - `formatConverted(amount, from, to, rates, locale?, rateDate?)`
    devolviendo `{ display, tooltip, isApprox, isMissing }`. Prefijo
    `≈` en el display + tooltip `"USD 100,00 a 1,234567 EUR/USD el
    YYYY-MM-DD"`. `isMissing` cuando falta una pata; el caller pinta
    badge en lugar de prefijo.
  - 11 tests nuevos cubren same/exact/inversión/composición/missing/
    NaN/rateDate.
- `packages/services/src/api/endpoints/currency.ts`: cliente del API
  (`currencyApi.rates(date)`, `currencyApi.convert(query)`).
- `packages/services/src/query/hooks/useCurrency.ts`:
  - `exchangeRatesQueryOptions(date)` — factory de opciones para
    `useQuery` y `useQueries` con la misma queryKey + parser.
  - `useExchangeRates(date)` envuelve el factory con
    `placeholderData: previous`. `staleTime` infinita para fechas
    pasadas (inmutables) y 1h para hoy.
- `packages/services/src/query/keys.ts`: `currency.rates(date)`.
- `packages/services/src/query/hooks/useDashboard.ts`: los 4 hooks
  aceptan `{ enabled }` para apagarse limpio cuando el toggle global
  cambia de modo.
- `packages/store/src/currency.ts`: nuevo campo `convertAll: boolean`
  (default `true`) + `setConvertAll`. Persistido en localStorage con
  versión 1 + función `migrate` que añade el campo a estados
  persistidos previos sin perderlos.

### Header — toggle "Convertir todas las monedas"

`apps/web/components/header/currency-menu.tsx` añade una row al pie
del dropdown con un toggle visual + caption "Suma cross-currency a
{activa}." Al pulsarlo se actualiza el store y todas las páginas
reaccionan en tiempo real (no hay refetch — la cache de tasas se
reusa).

### Vistas agregadas — Dashboard, Analysis, KPIs Transacciones

Patrón común (`useQueries` por moneda + helpers en
`apps/web/lib/cross-currency.ts`):

1. `useUserCurrencies()` → lista de monedas que el usuario tiene en
   BD.
2. `useExchangeRates(periodEndDate)` → mapa EUR→quote para fin del
   periodo.
3. `useQueries` lanza N llamadas a `/dashboard/summary|by-month|by-category`,
   una por moneda.
4. Helpers puros agregan: `aggregateSummaries`, `aggregateMonthly`,
   `aggregateByCategory`, `aggregateTopExpenses`. Cada bucket pasa
   por `convertAmount` y se acumula.

Cuando el toggle `convertAll` está OFF, los hooks single-currency
toman el relevo con `enabled: !convertAll` — comportamiento legacy
intacto.

Estimación de tráfico: con 1–3 monedas por usuario son 1–3
requests/page. Tras el primer fetch las tasas se cachean
indefinidamente (fechas pasadas son inmutables).

### Transactions table — tasa por fila (iteración tarde)

La columna **Importe** mantiene el valor original en su moneda y
añade debajo `≈ €X` muted con tooltip que incluye la **fecha real**
de la transacción.

- `transaction-list.tsx`:
  - Recoge `Set` de fechas distintas (`occurred_at` truncado a
    `YYYY-MM-DD`) de la página visible.
  - `useQueries` con `exchangeRatesQueryOptions(date)` por cada
    fecha distinta.
  - `Map<date, RatesMap>` indexa los resultados.
  - Cada fila usa el rates map de su día — tasa históricamente
    correcta para esa transacción.
- Coste: con paginación 20 + datos típicos en ~5–10 fechas → 5–10
  fetches en frío, 0 en caliente. Tras un scroll completo todas
  las fechas relevantes están en cache infinita.

## Flujo técnico (modo cross-currency, default)

```
 Header [CurrencyMenu]
    │ activeCurrency, convertAll
    ▼
 Page (Dashboard / Analysis / Transactions)
    ├── useUserCurrencies()              ─▶ ['EUR', 'USD']
    ├── useExchangeRates(periodEndDate)  ─▶ { USD: 1.18, GBP: 0.84, ... }
    └── useQueries x N  per-source-currency
            │
            ▼
        per-currency slices: [{ currency: 'EUR', data }, { currency: 'USD', data }]
            │
            ▼
        aggregate*(slices, toCurrency, rates)
            ├── convertAmount per bucket (composición vía EUR)
            └── sum + emit single result in active currency
            │
            ▼
        StitchKpiRow / StitchBalanceChart / StitchExpenseBreakdown ...

 Transactions table:
    ├── uniqueDates from visible items
    ├── useQueries x M (M = unique dates) → ratesByDate
    └── per-row formatConverted(amount, currency, active, ratesByDate[rowDate])
```

## Archivos clave

- `backend/app/modules/currency/router.py` — `_maybe_lazy_fetch` +
  hook en `/rates` y `/convert`.
- `backend/tests/test_currency_router.py` — 3 tests del lazy fetch.
- `packages/ui/src/format.ts` — `convertAmount`, `formatConverted`,
  `RatesMap`.
- `packages/ui/src/format.test.ts` — 11 tests nuevos.
- `packages/services/src/api/endpoints/currency.ts` — `currencyApi`.
- `packages/services/src/query/hooks/useCurrency.ts` —
  `exchangeRatesQueryOptions`, `useExchangeRates`.
- `packages/services/src/query/keys.ts` — `currency.rates(date)`.
- `packages/services/src/query/hooks/useDashboard.ts` — `enabled` flag.
- `packages/store/src/currency.ts` — `convertAll` + persist v1.
- `apps/web/components/header/currency-menu.tsx` — toggle UI.
- `apps/web/lib/cross-currency.ts` — aggregation helpers puros.
- `apps/web/app/(app)/dashboard/page.tsx`
- `apps/web/app/(app)/personal-finance/analysis/page.tsx`
- `apps/web/components/transactions/stitch-transactions-kpi-row.tsx`
- `apps/web/components/transactions/transaction-list.tsx` — tasa por fila.

## Endpoints añadidos

Ninguno. Se reusan `/currency/rates`, `/currency/convert` (de 8.1) y
`/dashboard/*`. El endpoint `/currency/rates` ahora hace lazy fetch
internamente cuando la fecha pedida no está en BD.

## Migraciones

Ninguna.

## Verificación

- [x] `pnpm typecheck` verde.
- [x] `pnpm lint` verde.
- [x] `pnpm test` — 11 nuevos en `@finanzas/ui` (22→33 si se cuenta
      el set previo, 11 nuevos para conversión/format).
- [x] `pytest backend/tests` — 149/149 (3 nuevos lazy-fetch).
- [x] Smoke manual con datos reales: dashboard sumando EUR+USD,
      tabla con `≈` por fila usando la tasa del día de cada
      transacción, toggle ON/OFF refleja inmediato sin refetch.

## Decisiones tomadas

- **Frontend convierte client-side, no backend**. La suma cross-
  currency vive en `lib/cross-currency.ts`. Razón: cambiar la moneda
  activa o el toggle no requiere refetch — la cache de tasas
  (`staleTime: Infinity` para pasado) se reusa. Trade-off: N
  peticiones por moneda al backend; aceptable para 1–3 monedas
  típicas. Con muchas monedas el coste se acumula y será PHASE-8.3.
- **Tasa de fin de periodo en agregados**. Los endpoints
  `/dashboard/*` devuelven sumas planas que ya pierden la fecha
  individual de cada transacción del bucket. Aproximamos con la
  tasa del fin del periodo (o hoy si incluye hoy). Es una
  simplificación deliberada — para totales anuales el error es
  bajo. La precisión per-tx en agregados es PHASE-8.3.
- **Tasa por fila en la tabla**. Aquí sí tenemos la fecha de cada
  fila → conversión histórica correcta usando `useQueries` sobre
  fechas distintas. Cache infinita amortiza el coste tras la
  primera vista.
- **Toggle "Convertir todas las monedas" default ON**. La
  motivación de la fase es que la app sume cross-currency por
  defecto. Quien quiera el comportamiento previo (filtro estricto
  por moneda activa) lo desactiva.
- **`convertAll` persistido con migrate v1**. Sin el migrate, un
  cliente con `localStorage` de PHASE-7.6 (sin el campo) inicializaría
  `convertAll = undefined` y rompería el toggle. Migrate inyecta
  `true` (default) sin perder la moneda.
- **Lazy fetch swallow**. `/currency/rates` no debe fallar 5xx
  cuando frankfurter está offline — los datos del usuario siguen
  visibles, sólo no se convierten. La UI muestra "≈ —" para
  señalizar la ausencia.
- **`fetched_at` no se actualiza en upsert**. La columna refleja
  cuándo se trajo la tasa la primera vez; el `source` indica si fue
  snapshot o frankfurter. Para auditoría real haría falta un
  `updated_at` separado, pero no es necesario en MVP.

## Limitaciones conocidas

- **Agregados usan tasa única por periodo**. Una transacción de
  marzo 2024 en USD se convierte con la tasa de fin de año en el
  Dashboard. PHASE-8.3 lo arreglará moviendo la conversión a SQL
  (JOIN `exchange_rates ON occurred_at`) y agregando post-conversión.
- **N peticiones por moneda en cada vista agregada**. Mientras
  PHASE-8.3 no llegue, el usuario con 4+ monedas verá un poco más
  de tráfico al cambiar año/periodo.
- **Cron nocturno de refresh**: no existe. El lazy fetch lo
  resuelve "al primer uso del día"; si nadie abre la app, las
  tasas no se actualizan. Aceptable por ahora.
- **Tabla: una request por fecha distinta visible**. Con
  paginación 200 y datos muy dispersos, peor caso 200 fetches.
  En la práctica las transacciones se concentran en pocos días al
  mes → 5–15 fetches típicos.
- **JPY**: el redondeo a 2 decimales es genérico. JPY usa 0
  decimales en producción real; no hemos visto datos JPY todavía.

## Próxima fase

PHASE-8.3 — Per-transaction conversion en backend. Mueve la
conversión a SQL para que los agregados también usen la tasa del
día de cada transacción. El frontend simplifica: borra
`cross-currency.ts` + los `useQueries` de las páginas; las páginas
vuelven a hacer un único `useDashboardSummary({target_currency})`.
Plan en [phase-8-roadmap.md](phase-8-roadmap.md) (sub-fase opcional
8.3).
