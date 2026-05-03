# PHASE-8 — Multimoneda con conversión global

> Planning doc. Aún no implementada. Este documento se va vaciando a
> medida que cada sub-fase se entrega y crea su propio
> `phase-8.X-*.md`.

## Origen

A partir de PHASE-7 la moneda activa es global (selector en el header,
persistida en `useCurrencyStore`). Pero las vistas que filtran por
moneda (Dashboard, Análisis, KPIs de Transacciones) sólo ven los
registros que coinciden exactamente con la moneda activa: si el
usuario tiene `EUR` y `USD`, al filtrar por `EUR` los gastos en
`USD` desaparecen del total. El usuario se queda con dos lecturas
parciales en lugar de una imagen real de su patrimonio.

PHASE-8 introduce conversión a la moneda activa usando tasas de cambio
históricas. La transacción se sigue almacenando en su moneda original
(audit trail intacto); la conversión vive en una capa de presentación
que la marca claramente como un valor derivado.

---

## Principios no negociables

1. **No mutar importes en BD**. La transacción guarda su `amount` y
   `currency` originales para siempre. Convertir al guardar destruiría
   la trazabilidad y obligaría a re-migrar si la tasa cambia.
2. **Tasa del día de la transacción**, no la actual. Convertir un café
   de 2022 con la tasa de hoy distorsiona la realidad y produce KPIs
   históricos engañosos.
3. **Privacidad mantenida**. Las tasas se obtienen de una fuente
   pública anónima (ECB vía `frankfurter.app` — proxy open-source que
   no requiere API key, no exige user-agent identificable, y no
   persiste consultas). El fetch no contiene datos del usuario, así
   que es compatible con el principio "datos NUNCA salen del equipo".
   Para uso 100% offline, se shippea un snapshot semanal embebido y
   el fetch online es opcional.
4. **Decimal estricto**. Toda multiplicación de tasa usa `Decimal` con
   precisión suficiente y rounding controlado (`ROUND_HALF_EVEN`,
   banker's rounding). `float` sigue prohibido.
5. **UI honesta**. El usuario tiene que distinguir un valor original
   de uno convertido. Se marca con prefix `≈` y tooltip que explica
   `USD 100,00 a 0,9234 EUR/USD del 2026-03-15`.

---

## Dependencias y orden

```
8.1  Currency rates backend (tabla + fetch + service)
  └─ 8.2  Conversion frontend (display layer + KPIs unificados)
```

8.1 desbloquea 8.2. No se puede fragmentar más sin que cada parte sea
útil por separado: el backend solo no aporta UX, el frontend solo no
tiene tasas que aplicar.

---

## PHASE-8.1 — Currency rates backend

**Branch**: `feat/phase-8.1-currency-rates`
**Backend con migración. Sin frontend.**

### Módulo nuevo `backend/app/modules/currency/`

Cross-cutting (igual que `auth/` y `ai/`) — cualquier módulo de dominio
puede importar `currency.service`. Estructura estándar:

```
currency/
├── __init__.py
├── router.py        # GET /currency/rates, GET /currency/convert (utilidad)
├── service.py       # convert(), get_rate(), refresh_rates()
├── repository.py    # SELECT rate FROM exchange_rates WHERE ...
├── client.py        # cliente HTTP de frankfurter.app
├── models.py        # ExchangeRate (SQLAlchemy)
└── schemas.py       # ExchangeRateResponse, ConvertRequest/Response
```

### Schema

Migración nueva: tabla `exchange_rates`. **Sin `user_id`** — los datos
son públicos y globales, no aplica aislamiento multi-tenant.

```sql
CREATE TABLE exchange_rates (
    rate_date  DATE        NOT NULL,
    base       CHAR(3)     NOT NULL,            -- 'EUR' (siempre EUR como base)
    quote      CHAR(3)     NOT NULL,
    rate       NUMERIC(20,8) NOT NULL,          -- 1 base = rate quote
    source     VARCHAR(32) NOT NULL DEFAULT 'frankfurter',
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (rate_date, base, quote)
);

CREATE INDEX ix_exchange_rates_quote_date ON exchange_rates (quote, rate_date);
```

Convención: **EUR es siempre la base**. La tasa USD↔GBP se calcula
componiendo (`USD/EUR * EUR/GBP`). Esto reduce la matriz N×N a N
filas por día y se alinea con cómo publica los datos el ECB.

### Servicio de conversión

```python
def convert(
    amount: Decimal,
    *,
    from_currency: str,
    to_currency: str,
    at_date: date,
) -> ConversionResult:
    """
    ConversionResult { amount: Decimal, rate: Decimal, rate_date: date,
                       fallback: Literal["exact", "previous", "missing"] }
    """
```

- Si `from == to` → returns amount con `fallback="exact"`.
- Lookup tasa exacta para `at_date`. Si existe → `exact`.
- Si no, busca la última tasa anterior (límite: 14 días). Si la
  encuentra → `previous`. Eso cubre fines de semana / festivos cuando
  el ECB no publica.
- Si no hay nada en 14 días → `missing` con `rate=Decimal("1")` y la
  capa que llama decide cómo señalizarlo (UI muestra "—" o tag
  "sin tasa").

### Cliente HTTP

`client.py` usa `httpx` (ya está como dep del módulo `ai`). Llama a
`https://api.frankfurter.app/{date}?from=EUR&to=USD,GBP,JPY,...`. La
lista de monedas a fetchear se calcula una vez al día desde
`SELECT DISTINCT currency FROM transactions` ∪ `BASE_CURRENCIES`
(EUR + USD).

Sin API key, sin user-agent custom, sin auth. Rate limit ~10 req/s
según docs de frankfurter; nuestro patrón (1 fetch/día/usuario en el
peor caso) está muy por debajo.

### Refresco de tasas

Tres triggers, en orden de simplicidad:

1. **Lazy on-demand**: cuando un endpoint de dashboard/analysis pide
   convertir y la fecha pedida no está en BD → fetch + persist + reuso.
   Esto cubre el flujo nominal sin cron.
2. **Backfill al crear transacción nueva**: al INSERT en
   `transactions`, encolamos un fetch para `(occurred_at, currency)`
   si la tasa aún no existe. Background task con `BackgroundTasks` de
   FastAPI; si falla el fetch, no bloquea la creación.
3. **Snapshot embebido**: `backend/app/modules/currency/seeds/` contiene
   un dump CSV con tasas EUR↔(USD,GBP,JPY,CHF,CAD,AUD,MXN,BRL,CNY)
   para los últimos 5 años. La migración 8.1 lo carga si la tabla
   está vacía. Esto deja la app utilizable sin red la primera vez.

### Endpoints

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET    | `/currency/rates?date=YYYY-MM-DD` | sí | Lista tasas EUR→X para la fecha (o hoy). Útil para debug/UI. |
| GET    | `/currency/convert?from=&to=&amount=&date=` | sí | Conversión puntual (no se usará desde el frontend si la conversión vive client-side, pero útil para integraciones). |
| POST   | `/currency/refresh` | sí (admin) | Forzar fetch de hoy. Se decide en 8.1 si exponerlo o dejarlo solo como CLI. |

### Tests

- `test_currency_service.py` — convert exact/previous/missing,
  rounding, composición no-EUR (USD→GBP via EUR).
- `test_currency_repository.py` — lookup con fallback de 14 días.
- `test_currency_client.py` — mock httpx, parse de la respuesta de
  frankfurter, manejo de error de red.
- `test_currency_seeds.py` — la migración carga el snapshot y queda
  consultable.

### Verificación

- [ ] `pytest backend/tests/` verde con tests nuevos.
- [ ] `mypy app/` verde.
- [ ] Snapshot embebido se carga en BD limpia.
- [ ] `GET /currency/convert?from=USD&to=EUR&amount=100&date=2026-03-15`
      devuelve un valor con la tasa real del ECB de ese día.

### Riesgos

- **frankfurter.app va offline o cambia su API**. Mitigación: el
  snapshot embebido cubre el camino crítico, y el cliente HTTP queda
  aislado tras `currency.client` — sustituirlo por otra fuente (ECB
  XML directo, exchangerate.host) es un cambio acotado.
- **Composición de tasas no-EUR introduce error de redondeo**.
  Mitigación: hacer la composición a precisión interna mayor (e.g.,
  10 decimales) y redondear sólo al final con `ROUND_HALF_EVEN` a 2
  decimales.

**Estimación**: 1.5-2 días.

---

## PHASE-8.2 — Conversion frontend (display layer)

**Branch**: `feat/phase-8.2-currency-display`
**Frontend. Sin migración, sin endpoints nuevos** (consume los de 8.1).

### Capa de presentación

Nuevo helper en `packages/ui/src/format.ts`:

```ts
formatConverted(amount: Decimal | string, opts: {
  fromCurrency: string;
  toCurrency: string;
  rate: number;
  rateDate: string;
  fallback: 'exact' | 'previous' | 'missing';
}): { display: string; tooltip: string; isApprox: boolean }
```

Devuelve `{ display: '≈ €1.234,56', tooltip: 'USD 1.400,00 a 0,8821 EUR/USD del 2026-03-15', isApprox: true }`.

Si `fromCurrency === toCurrency` → `isApprox: false`, sin tooltip,
sin prefijo `≈`.

### Servicio: nuevo hook

`packages/services/src/api/endpoints/currency.ts`:

```ts
useExchangeRates(date: string)  // GET /currency/rates?date=...
```

Devuelve un map `{ [code: string]: number }` (todas las cotizaciones
EUR→X para esa fecha). Cache fuerte (`staleTime: Infinity`) — la tasa
de un día pasado no cambia.

### Refactor de pantallas afectadas

Tres pantallas miran `currency`:

1. **Dashboard** (`/dashboard`, `apps/web/app/(app)/dashboard/page.tsx`).
   - KPIs y gráfica suman ahora **todas** las transacciones,
     convirtiendo cada una a la moneda activa.
   - Backend cambio mínimo: `dashboard.repository` deja de filtrar por
     `currency` y devuelve grupos por mes con un breakdown opcional
     `(currency, amount)`. La conversión vive client-side aprovechando
     el cache de `useExchangeRates`. Alternativa: que el backend haga
     la conversión usando `currency.service` y devuelva ya en moneda
     destino — más simple para frontend pero menos cacheable.
2. **Análisis** (`/personal-finance/analysis`).
   - Mismo patrón. El "Income vs Expenses" gráfico apila series por
     mes con todo convertido.
   - El desglose por categoría suma transacciones aunque estén en
     monedas distintas.
3. **Transacciones** (`/personal-finance/transactions`).
   - **No** se convierte la columna `amount` de la tabla — cada fila
     se muestra siempre en su moneda original (audit trail visible).
   - **Sí** se añade una columna secundaria muted "≈ €X" para filas
     en moneda distinta a la activa.
   - Los KPIs de la cabecera (`StitchTransactionsKpiRow`) sí suman
     todo convertido.

### Decidir antes de implementar

- **Backend convierte vs frontend convierte**: lo natural es que
  el backend responda ya en moneda destino para el dashboard
  (queries más simples y menos round-trips). Pero eso obliga a
  re-fetch al cambiar el selector global. Frontend client-side con
  cache de tasas se siente mejor para el UX en vivo. Recomendación:
  **frontend convierte**, el backend devuelve agregados por moneda.
- **Tooltip vs sidebar**: ¿el detalle de tasa va en tooltip al hover
  (compacto) o en una pequeña popover al click (más descubrible y
  accesible)? Recomendación: tooltip nativo del navegador con
  fallback ARIA — barato y suficiente para MVP.
- **Modo "mononeda" como toggle**: ¿permitir al usuario decir "no
  conviertas, muéstrame solo lo de mi moneda activa"? Útil para
  auditoría ("quiero ver SOLO mis EUR"). Recomendación: añadir un
  switch sutil "Convertir todas las monedas a EUR" en el menú de
  moneda del header, default ON.

### Tests

- `format.test.ts` — `formatConverted` casos `exact/previous/missing`
  y `from===to`.
- `currency.test.ts` — `useExchangeRates` cache + invalidación al
  cambiar fecha.
- Tests de los componentes Stitch que usan importes monetarios para
  asegurar que reciben el valor convertido y muestran el `≈` cuando
  procede.

### Verificación

- [ ] `pnpm verify` verde.
- [ ] Dashboard con un mix EUR + USD muestra un total único.
- [ ] La tabla de transacciones muestra valores originales con
      conversión muted al lado.
- [ ] Cambiar la moneda en el header recalcula sin refetch (cache
      hit en `useExchangeRates`).
- [ ] Toggle "Convertir todas las monedas" desactiva la suma cross-
      currency y vuelve al filtrado actual.

### Riesgos

- **Coste de conversión client-side**: para 5k transacciones × 12
  meses, son del orden de 60k multiplicaciones. Despreciable, pero
  hay que evitar recomputar en cada render — `useMemo` sobre
  `transactions × rates`.
- **Hidratación SSR**: el cache de TanStack Query y el store
  persistido pueden producir mismatch si el servidor renderiza con
  EUR y el cliente hidrata con USD persistido. Mitigación: las
  vistas siguen siendo `'use client'` (ya lo son) y el SSR sólo
  renderiza el shell.

**Estimación**: 2 días.

---

## Definition of Done de la fase 8 completa

- [ ] PHASE-8.1 mergeada con tests + snapshot embebido.
- [ ] PHASE-8.2 mergeada con todas las pantallas convirtiendo.
- [ ] Doc `internal_docs/api/endpoints.md` actualizado con
      `/currency/*`.
- [ ] Doc `internal_docs/data-model/schema.md` actualizado con
      `exchange_rates`.
- [ ] ADR `internal_docs/decisions/NNNN-currency-conversion.md` que
      registre las decisiones clave (EUR como base, fuente
      frankfurter, conversión client-side, tasa al día de la
      transacción).
- [ ] Smoke manual: importar transacciones en USD, cambiar la moneda
      activa a EUR, comprobar que los KPIs incluyen las USD ya
      convertidas con la tasa del día correcto.

---

## Próximas fases (post-8)

PHASE-8 cierra la promesa de "una imagen real del patrimonio" sin
romper la trazabilidad. Posibles iteraciones siguientes:

- PHASE-9 — Presupuestos por categoría con alertas (independiente).
- PHASE-10 — Recurrencias / suscripciones detectadas automáticamente
  desde el patrón de transacciones (independiente).
- Sub-iteración 8.3 (opcional) — backfill bulk de tasas para
  transacciones importadas en lote, mostrando progreso. Sólo si los
  triggers lazy + on-create de 8.1 dejan huecos visibles en imports
  grandes.
