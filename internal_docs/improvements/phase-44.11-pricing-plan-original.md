# PHASE-44.8 — Pricing: cotizaciones (yfinance) + FX (BCE)

**Estado**: 📋 planificada
**Ámbito**: backend `modules/investment/pricing/` completo + integración en
la valoración de cartera. Sin UI nueva (la Tab Cartera consume el payload).
**Documentos padre**: `ARCHITECTURE-investment-module.md` (§ pricing, §5.1
contrato de summary, §8.1 política staleness-tolerant) y `DESIGN-v2` §3/§9.
**Decisiones ya tomadas (no reabrir)**: adapter primario **yfinance**
(multi-mercado US+LSE+BME+XETRA+Euronext, coste 0, no oficial — riesgo
absorbido por el diseño staleness-tolerant); **EODHD** como fallback de pago
documentado, NO se implementa; FX = **tipos de referencia del BCE**;
**prohibido** scraping HTML, websockets, histórico de precios, cron/scheduler.

---

## 0. Reglas duras

1. El adapter es la ÚNICA pieza que conoce yfinance. Service/repository/router
   trabajan contra el Protocol `PriceAdapter` y el dataclass `Quote`.
2. **Nunca se persiste `GBp`**. LSE cotiza en peniques: el adapter divide /100
   y emite `currency='GBP'`. Assert en el adapter + test.
3. Fallo de proveedor → se sirve la última quote persistida; `quote_stale` se
   **calcula** en respuesta (`fetched_at` > TTL), no se almacena. Nunca se
   bloquea la vista de cartera por un proveedor caído.
4. Posición sin quote (símbolo no resoluble, exchange sin sufijo conocido) →
   `market_value = null`, excluida de los totales, badge "sin cotización" con
   razón. Jamás valorar a coste como fallback silencioso.
5. Sin red en CI: el adapter se testea con fixtures/monkeypatch. Verificación
   viva = script smoke manual.
6. Decimal en todo; el redondeo solo en presentación.

---

## 1. Dependencias

- `yfinance` **pineada a la última estable en el momento de implementar**
  (anotar la versión exacta en este doc al cerrar la fase). Trae `curl_cffi`
  como transitiva — esperable en el lockfile.
- HTTP para FX: reutilizar el cliente HTTP ya presente en el repo (httpx).
  Sin dependencias nuevas para el BCE.

---

## 2. Sub-fases

### 44.8.A — Esquema y modelos

- Verificar si la migración de `price_quotes` existe (estaba en el DDL de §2
  del ARCHITECTURE desde el inicio). `fx_rates` se añadió después: **casi
  seguro falta** → migración aditiva:

```sql
CREATE TABLE fx_rates (
  date DATE NOT NULL,
  pair CHAR(6) NOT NULL,          -- 'USDEUR' = 1 USD → rate EUR
  rate NUMERIC(16,8) NOT NULL,
  source VARCHAR(16) NOT NULL DEFAULT 'ECB',
  PRIMARY KEY (date, pair)
);
```

- Modelos SQLAlchemy `PriceQuote` (una fila viva por security, UNIQUE
  security_id) y `FxRate`; repositorios con upsert.
- **Salida**: `alembic upgrade/downgrade` reversibles; tests de modelo.

### 44.8.B — Adapter yfinance

`pricing/adapters/base.py`:

```python
@dataclass(frozen=True)
class Quote:
    price: Decimal
    prev_close: Decimal | None
    currency: str            # ISO real: 'USD'|'EUR'|'GBP'... jamás 'GBp'
    as_of: datetime          # timestamp del dato según proveedor (aprox ok)

class PriceAdapter(Protocol):
    async def quotes(self, symbols: Sequence[str]) -> dict[str, Quote | QuoteError]: ...
    async def symbol_search(self, q: str) -> list[SymbolHit]: ...
```

`pricing/adapters/yfinance.py`:

- **Mapeo símbolo Yahoo desde `(ticker, exchange)`** — pieza nueva y crítica.
  Tabla de sufijos en el adapter:
  `{'NYSE': '', 'NASDAQ': '', 'LSE': '.L', 'BME': '.MC', 'XETRA': '.DE',
    'EPA': '.PA', 'AMS': '.AS', 'EBR': '.BR', 'MIL': '.MI', 'SWX': '.SW',
    'VIE': '.VI', 'LIS': '.LS'}`.
  Exchange fuera de la tabla → `QuoteError("exchange sin mapeo yfinance")` →
  la posición queda "sin cotización" con esa razón visible. **No inventar
  sufijos**: si aparece un exchange nuevo, punto de parada (§5).
- Lectura vía `Ticker.fast_info` (`last_price`, `previous_close`,
  `currency`) — NO parsear `.info` completo (pesado y volátil).
- Batch con `yf.Tickers(" ".join(symbols))`; **throttling ~1 req/s** entre
  llamadas de red y ejecución serializada (sin gather masivo): somos
  huéspedes no oficiales.
- Normalización `GBp`/`GBX` → precio/100, currency `GBP` (también
  `prev_close`). `ZAc` análogo si apareciera (÷100 → ZAR).
- Timeouts y captura de excepciones por símbolo → `QuoteError(reason)` sin
  tumbar el batch.
- **Salida**: unit tests con monkeypatch de fast_info: caso US, caso LSE en
  peniques (assert /100 y 'GBP'), caso exchange sin mapeo, caso excepción de
  red → QuoteError.

### 44.8.C — FX BCE

`pricing/adapters/ecb_fx.py`:

- Fuente de datos: **tipos de referencia diarios del BCE** (publicación días
  hábiles ~16:00 CET). Transporte: API Frankfurter (sirve exactamente los
  datos BCE, JSON, sin key) con la URL base en constante; si en
  implementación diera problemas, alternativa equivalente: endpoint SDMX/CSV
  del propio BCE. `fx_rates.source = 'ECB'` en ambos casos.
- `ensure_rates(pairs: set[str], as_of: date)` en el service: garantiza fila
  del último día hábil ≤ as_of para cada par necesario (`USDEUR`, `GBPEUR`;
  EUR→EUR no genera fila, rate 1 implícito). Fin de semana/festivo/antes de
  la publicación → se usa el último disponible; la fecha del tipo aplicado
  viaja en el payload (`fx_as_of`).
- Conversión: `value_eur = value_native × rate(native→EUR)`. Convención del
  par: `XXXEUR` = 1 XXX → rate EUR. Documentar en docstring y test.
- **Salida**: tests con fixture de respuesta (sin red); caso fin de semana →
  toma viernes; caso par EUR → sin lookup.

### 44.8.D — Política de refresh + endpoints

`pricing/refresh.py` + `service.py` + `router.py`:

- **On-access**: al construir la valoración de cartera, recolectar securities
  con quote ausente o `fetched_at` > `PRICE_TTL_HOURS` → un solo batch al
  adapter → upsert. Fallos parciales: se conserva la fila vieja (regla dura
  #3).
- **Manual**: `POST /investment/pricing/refresh {security_ids?: [...] |
  "all_portfolio"}` — ignora TTL, mismo camino de código.
- FX se asegura en el mismo paso (`ensure_rates`) para las divisas presentes
  en cartera.
- Config (env): `PRICE_PROVIDER=yfinance` (solo informativo/selector),
  `PRICE_TTL_HOURS=24` (poner 1 para refresco horario — decisión del
  usuario en runtime, no del código).
- **Salida**: tests de la política TTL (fresco → no llama adapter; caducado →
  llama; fallo → conserva y marca stale); idempotencia del refresh manual.

### 44.8.E — Integración en la valoración (contrato §5.1)

Donde viva el summary de cartera (si la fase de portfolio aún no está: esta
sub-fase entrega el service de valoración y el wiring se completa allí):

- Por posición: `last_price`, `quote_as_of`, `quote_stale`, `market_value`
  nativa y EUR (con `fx_as_of`), `daily_change` = qty × (last − prev_close),
  descomposición unrealized en `price_effect`/`fx_effect` según §5.1.
- Posición sin quote → excluida de totales + badge con razón (regla #4).
- Nivel cartera: totales, exposición por divisa (ya calculable con el fx).
- **Salida**: tests de contrato: cartera mixta USD/GBP/EUR con fixtures;
  posición sin mapeo excluida de totales; daily_change correcto; stale
  propagado.

### 44.8.F — symbol_search

- Implementar `symbol_search` del Protocol con la búsqueda de yfinance
  (`yf.Search`/`Lookup`), mapeando a `SymbolHit {ticker, exchange, name}`
  para el flujo de `GET /investment/securities/search` (§5 ARCHITECTURE).
- **Punto de parada**: si la calidad de resultados es pobre en la prueba
  manual (típico: exchanges EU mal etiquetados), NO improvisar un segundo
  proveedor — preguntar al usuario si activa la key gratuita de Finnhub
  SOLO para search (decisión ya prevista, opcional).

### 44.8.G — Smoke vivo + cierre

- `scripts/pricing_smoke.py`: fuera de CI, golpea yfinance y BCE de verdad
  con 4-5 símbolos (uno por mercado: p. ej. KO, ULVR.L, IBE.MC, ALV.DE,
  MC.PA) e imprime price/prev/currency/fx aplicado. Verificación manual del
  usuario contra su broker.
- Anotar en este doc la versión pineada de yfinance y cualquier sufijo de
  exchange añadido.

---

## 3. Verificación global

- [ ] `pytest` verde; **cero llamadas de red en CI** (grep de httpx/yfinance
      en tests → todo mockeado).
- [ ] Assert imposible persistir `currency='GBp'` (test dedicado).
- [ ] Cartera con posición sin mapeo: summary responde 200, posición listada
      con badge y fuera de totales.
- [ ] Proveedor caído (adapter lanza): summary responde 200 con quotes stale
      marcadas.
- [ ] `downgrade` de la migración fx_rates limpio.
- [ ] Smoke manual ejecutado por el usuario y contrastado con su broker
      (precios ±delay razonable, divisas correctas, EUR bien convertido).

## 4. Puntos de parada obligatoria

(a) Exchange presente en la cartera del usuario sin sufijo en la tabla →
preguntar, no inventar. (b) Calidad de symbol_search insuficiente → preguntar
antes de añadir Finnhub-search. (c) Cualquier campo de fast_info que llegue
vacío/raro de forma sistemática en un mercado → documentar y preguntar antes
de cambiar la fuente del campo.

## 5. Fuera de alcance

Histórico de cotizaciones y charts · websocket/tiempo real · scheduler ·
adapter EODHD (solo documentado como fallback) · precios de BTC (módulo
bitcoin, resuelto con Kraken) · UI nueva más allá de consumir el payload.
