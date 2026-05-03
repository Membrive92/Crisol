# PHASE-8.1 — Currency rates backend

**Estado**: ✅ completada
**Rama**: `feat/phase-8.1-currency-rates`
**PR**: —
**Fecha de merge**: 2026-05-03

## Objetivo

Cimentar el backend de conversión multimoneda. Tras PHASE-7.6 la
moneda activa es global en el frontend pero las vistas siguen
filtrando por moneda exacta. PHASE-8.1 entrega la infraestructura
necesaria para que PHASE-8.2 sume cross-currency: tabla de tasas
históricas, cliente al ECB vía `frankfurter.app`, servicio de
conversión con `Decimal` + banker's rounding, snapshot embebido para
arrancar offline.

## Qué se implementó

### Módulo `backend/app/modules/currency/`

Cross-cutting (mismo nivel que `auth/`, `ai/`). Estructura interna:

```
currency/
├── __init__.py
├── models.py          # ExchangeRate
├── schemas.py         # ConversionResult, ConvertResponse, RatesResponse, ExchangeRateRow, RateFallback
├── repository.py      # get_rate, get_rate_with_fallback, list_rates_for_date, upsert_rates, list_distinct_quotes
├── client.py          # frankfurter.app (httpx)
├── service.py         # convert, refresh_rates, ensure_rate
├── router.py          # GET /currency/rates, GET /currency/convert
├── exceptions.py      # FrankfurterUnavailableError, FrankfurterInvalidResponseError
└── seeds/
    ├── __init__.py    # load_snapshot()
    └── rates.csv      # snapshot offline 2024-2026 × 9 monedas
```

### Schema

Tabla nueva `exchange_rates`:

| Columna     | Tipo            | Notas                                            |
|-------------|-----------------|--------------------------------------------------|
| rate_date   | DATE            | PK compuesta                                     |
| base        | CHAR(3)         | PK; siempre 'EUR' por convención                 |
| quote       | CHAR(3)         | PK                                               |
| rate        | NUMERIC(20, 8)  | precisión amplia; redondeo final lo hace service |
| source      | VARCHAR(32)     | 'frankfurter' / 'snapshot' / 'test'              |
| fetched_at  | TIMESTAMPTZ     | server_default `now()`                           |

Índice secundario `ix_exchange_rates_quote_date(quote, rate_date)`
para acelerar las queries de "última tasa conocida para X".

**Sin `user_id`**: las tasas son datos públicos globales (ECB), no
aplica aislamiento multi-tenant.

### Cliente HTTP

`client.fetch_rates(target_date, base, quotes)` hace
`GET https://api.frankfurter.app/{date}?from={base}&to={csv}`.
Parsea la respuesta y devuelve `dict[str, Decimal]` (vía `str(value)`
para no perder precisión por float).

frankfurter.app es un proxy open-source del feed diario del ECB:
sin API key, sin user-agent identificable, sin tracking. Sólo
viajan fechas y códigos ISO 4217 públicos — compatible con el
principio "los datos del usuario nunca salen del equipo".

### Servicio de conversión

`service.convert(amount, from_currency, to_currency, at_date)`:

1. Si `from == to` → devuelve amount con `fallback="same"`.
2. Resuelve EUR→from y EUR→to vía `_resolve_eur_rate`:
   - Tasa exacta para `at_date` → `"exact"`.
   - Última conocida en ventana de 14 días → `"previous"`.
   - Nada → `None`.
3. Si alguna pierna no resuelve → `fallback="missing"`, amount sin
   convertir, rate=1. El caller decide cómo señalizarlo.
4. Composición: `rate(FROM→TO) = rate(EUR→TO) / rate(EUR→FROM)`,
   matemáticamente equivalente a tener tasas directas.
5. Multiplicación a precisión completa de `Decimal`. Redondeo único
   al final con `ROUND_HALF_EVEN` a 2 decimales (`NUMERIC(14, 2)`).
6. `effective_date = min(src_date, dst_date)` — la pierna más
   rancia limita la frescura del resultado.

### Refresco

Tres triggers (los dos primeros se cablean en PHASE-8.2 cuando
existan callers reales; el tercero ya está activo):

1. **Lazy on-demand**: `service.ensure_rate(quote, at_date)`
   chequea si hay tasa exacta y, si no, intenta refrescar. Devuelve
   bool indicando si tras el refresco hay tasa.
2. **Background al crear transacción**: hook desde
   `transactions.service.create_transaction` que encole un
   `ensure_rate(currency, occurred_at)`. Pendiente de cablear.
3. **Snapshot embebido**: `currency/seeds/rates.csv` con tasas
   EUR→{USD, GBP, JPY, CHF, CAD, AUD, MXN, BRL, CNY} para 6 fechas
   anchor (Enero/Julio 2024-2026). La migración carga el snapshot
   en bulk al primer `alembic upgrade head` para que la app sea
   utilizable sin red. Los upserts posteriores con
   `source='frankfurter'` reescriben sobre el snapshot.

### Endpoints añadidos

| Método | Ruta | Auth | Body / Query | Response |
|--------|------|------|--------------|----------|
| GET    | `/currency/rates` | sí | `?date=YYYY-MM-DD&base=EUR` | `RatesResponse` |
| GET    | `/currency/convert` | sí | `?amount=&from=&to=&date=` | `ConvertResponse` |

Las tasas son datos públicos, pero el endpoint exige autenticación
para evitar que sea totalmente abierto. No hay endpoint
`/currency/refresh` administrativo en esta fase — el refresco
ocurre lazy desde `service.ensure_rate`. Si en operación real se
necesita forzar un fetch global, se añade en una iteración.

### Settings nuevos

```python
frankfurter_base_url: str = "https://api.frankfurter.app"
frankfurter_timeout_seconds: int = 10
```

## Flujo técnico

```
                       ┌──────────────┐
                       │ caller módulo│
                       └──────┬───────┘
                              │ service.convert(amount, from, to, at_date)
                              ▼
                  ┌────────────────────────┐
                  │ currency.service       │
                  │ ┌────────────────────┐ │
                  │ │ _resolve_eur_rate  │ │
                  │ │  - exact ?         │ │
                  │ │  - previous (14d)? │ │
                  │ └─────────┬──────────┘ │
                  └───────────┼────────────┘
                              │
                              ▼
                       ┌────────────┐
                       │ repository │
                       └─────┬──────┘
                             │
                             ▼
                       ┌────────────┐
                       │exchange_rates│
                       └────────────┘

  ─── refresco (lazy) ───
   service.ensure_rate(quote, at_date)
        ├─ ¿hay exacta en BD? → return True
        └─ no:  service.refresh_rates(at_date, [quote])
                ├─ client.fetch_rates → frankfurter.app
                ├─ repository.upsert_rates
                └─ devuelve número de filas
```

## Archivos clave

- `backend/app/modules/currency/__init__.py`
- `backend/app/modules/currency/{models,schemas,exceptions}.py`
- `backend/app/modules/currency/{repository,client,service,router}.py`
- `backend/app/modules/currency/seeds/{__init__.py,rates.csv}`
- `backend/alembic/versions/c5d28e7f3b91_currency_module.py`
- `backend/app/main.py` — registra `currency_router`
- `backend/app/core/config.py` — `frankfurter_*` settings
- `backend/tests/conftest.py` — registro del modelo `ExchangeRate`
- `backend/tests/test_currency_{client,repository,service,router}.py`

## Migraciones

`c5d28e7f3b91_currency_module.py` (down_revision `b27e391fa4c8`):
crea la tabla `exchange_rates`, el índice secundario y carga el
snapshot offline.

## Verificación

- [x] `pytest backend/tests/` — 146/146 (29 nuevos).
- [x] `ruff check app/ tests/` verde.
- [x] `mypy app/` — 3 errores pre-existentes en `ai/client.py`
      (PIL stubs); ningún error nuevo introducido por PHASE-8.1.
- [x] `alembic upgrade head` aplica la nueva revisión y carga el
      snapshot embebido.
- [x] Smoke contra frankfurter desactivado (todos los tests usan
      mock); el cliente real se valida cuando PHASE-8.2 monte la
      UI con conexión.

## Decisiones tomadas

- **EUR como base canónica almacenada**. Reduce la matriz N×N a N
  filas por día y se alinea con cómo publica el ECB. Las tasas
  X→Y se componen vía EUR.
- **Conversión vía service, no en repository**. El repository
  expone lookup atómico; la composición + redondeo + decisión de
  fallback son lógica de negocio.
- **`Decimal` con `ROUND_HALF_EVEN`**. Banker's rounding minimiza
  sesgo acumulado en agregaciones grandes (esencial para totales
  cross-currency en el dashboard). Multiplicación a precisión
  completa, redondeo SÓLO al final.
- **Ventana de fallback de 14 días**. Cubre fines de semana,
  festivos y periodos vacacionales bancarios sin recurrir al
  cliente HTTP.
- **`fallback: same` para `from == to`**. Distingue una conversión
  trivial de una real con tasa = 1, útil para que la UI no muestre
  "≈" cuando no hay conversión efectiva.
- **`fallback: missing` no lanza excepción**. Devuelve amount sin
  tocar para que el caller (UI) pueda mostrar el original con un
  badge "sin tasa" en vez de fallar duro.
- **Snapshot embebido + upsert idempotente**. El snapshot es una
  semilla pragmática (~54 filas) para que la app sea usable
  offline; el upsert por PK garantiza que el primer fetch real
  desde frankfurter sustituya las tasas anchor sin colisiones.
- **frankfurter sobre ECB XML directo**. frankfurter ya parsea el
  XML, expone JSON simple, soporta histórico por URL path, y es
  open-source. Cambiar de fuente queda contenido tras
  `currency.client`.
- **B008 + Annotated form**. Los `Query(default=None, alias=...)`
  de tipos `Optional` disparan B008 de ruff; los reescribimos a
  `Annotated[X | None, Query(alias=...)] = None`. El resto de
  Query con default literal pasa.

## Limitaciones conocidas

- `service.convert` redondea a 2 decimales. JPY usa 0 decimales
  en producción real; cuando llegue un usuario con JPY veremos si
  merece la pena hacer el `_QUANTIZE` dependiente de la moneda.
- Sin endpoint admin `/currency/refresh` ni cron job. El refresco
  on-create de transacciones queda pendiente de cablear desde
  `transactions.service` (es un hook trivial pero pertenece al
  scope de PHASE-8.2 cuando los datos de moneda se vuelvan
  visibles en cross-currency).
- Snapshot embebido cubre 6 fechas anchor 2024-2026. Cualquier
  fecha intermedia sin red caerá en `fallback="missing"` hasta
  que un fetch real la pueble. La ventana de 14 días no ayuda
  porque las anchors están separadas por 6 meses; es a propósito
  — el fallback no debe inventar tasas.
- frankfurter.app no provee tasas para fechas futuras (devuelve
  `latest`). El endpoint `convert` con `date` futura
  silenciosamente cae a la última tasa conocida de hoy y reporta
  `previous`. Aceptable para el MVP.
- Sin tests E2E contra frankfurter real (todos mockeados). Si la
  fuente cambia su API, los tests no lo detectarán; un smoke
  manual periódico mitiga.

## Próxima fase

PHASE-8.2 — Conversion frontend (display layer). Capa de
presentación con `formatConverted`, hook `useExchangeRates` con
`staleTime: Infinity`, refactor de Dashboard / Análisis / KPIs
de Transacciones para sumar cross-currency, toggle "Convertir
todas las monedas" en el menú de moneda del header.

Sub-iteración 8.3 (opcional, post-8.2): cablear el hook
on-create de transacciones para precargar la tasa del día,
exponer un endpoint admin `/currency/refresh` si el cron aparece
útil tras observar el comportamiento real.
