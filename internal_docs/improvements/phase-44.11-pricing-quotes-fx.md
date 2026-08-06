# PHASE-44.11 — Pricing: cotizaciones (yfinance) + FX vía `currency`

**Estado**: 🚧 implementada y verde en automatizado — **pendiente tu prueba
manual** (contrastar precios con el bróker) y el `--apply` del data-fix.
**Documentos hermanos**: `phase-44.11-pricing-decisiones.md` (el contraste
plan-vs-repo y el porqué de cada decisión — se conserva como registro) y
`ARCHITECTURE-investment-module.md` (ya parcheado: sin `fx_rates`, Protocol
quotes-only, yfinance primario).
**Decisiones aceptadas** (usuario, 2026-08-01): las seis del doc de
decisiones, con los tres matices integrados abajo. **No reabrir.**

---

## 0. Reglas duras

1. El adapter es la ÚNICA pieza que conoce yfinance. Service/repository/
   router trabajan contra `PriceAdapter` y `Quote`.
2. **Nunca se persiste `GBp`/`GBX`**: el adapter divide /100 y emite
   `currency='GBP'`. Assert + test de regresión con posición LSE.
3. **La divisa del quote es la del PROVEEDOR, no la del catálogo** [D4].
   `Quote.currency` viaja en el dataclass y es lo que se persiste. Si
   (tras normalizar) difiere de `Security.currency` → **quality flag
   visible en la posición** ("divisa del proveedor difiere del catálogo");
   se valora con la del proveedor. Silenciar la discrepancia está
   prohibido.
4. Fallo de proveedor → última quote persistida + `quote_stale` calculado
   (`fetched_at` > TTL). Nunca se bloquea la cartera.
5. Símbolo sin cobertura del proveedor activo (p. ej. `PRICE_PROVIDER=
   finnhub` con posición LSE/BME) → **exclusión estándar** "sin
   cotización" + razón, fuera de totales. **Nunca error del summary** [D3].
   El selector no cambia el contrato.
6. FX: **cero piezas nuevas**. Se consume el módulo transversal
   `currency` (`exchange_rates`, datos BCE, cron nocturno PHASE-11.1):
   `ensure_rates_for_dates` + `convert`, propagando `rate_date` al
   payload como `fx_as_of` [D1]. Prohibido crear tabla/cliente FX propio.
7. `symbol_search` **fuera de esta fase** [D2, ADR-0008]: `PriceAdapter`
   es quotes-only. La evaluación de yfinance como `SymbolSearchAdapter`
   ocurre después, en `catalog/adapters/symbol_search/`.
8. Sin red en CI; Decimal en todo; redondeo solo en presentación (el de
   divisa lo hace `currency.service`, JPY incluido).

---

## 1. Sub-fases (orden de ejecución)

### 44.11.0 — ADR (primero, bloquea el resto) [D1] ✅ (2026-08-02)

Cerrado: [ADR-0009](../decisions/0009-single-fx-source-currency-transversal.md)
+ `architecture.md` §6 corregido (`currency/` pasa a estar declarado
transversal; su ausencia de la lista era la ambigüedad). El ADR declara
además dos cosas que el plan no preveía y que salieron de leer
`currency/service.py`: **`ensure_rates_for_dates` hace `commit()` por
dentro** (llamarlo en mitad de una unidad de trabajo confirmaría
escrituras a medias) y **`convert()` con `fallback="missing"` devuelve el
importe SIN convertir con `rate=1`** — para una cartera eso son dólares
sumados como euros, así que degrada a exclusión estándar.

<details><summary>Alcance original</summary>

ADR corto que declare: (a) `exchange_rates` = **única fuente de tipos de
cambio de la aplicación**; (b) `currency` = módulo **transversal**
consumible desde módulos de dominio (aclara `architecture.md` §6, con el
precedente de los 5 importadores existentes en `personal_finance`); (c) la
sección `fx_rates` del ARCHITECTURE de inversión queda superseded (ya
parcheado).
**Salida**: ADR en `internal_docs/decisions/`, `docs-check` verde.
</details>

### 44.11.B — Adapter yfinance ✅ (2026-08-02)

- Dependencia `yfinance==1.5.2` **pineada**. Transitivas nuevas en el
  lockfile: `curl_cffi`, `requests`, `protobuf`, `peewee`, `pytz`,
  `multitasking`. `constraints.txt` regenerado desde `backend/.venv` —
  diff de **adiciones puras**, ningún pin existente movido.
- `Quote` con `price`, `prev_close`, **`currency`** (regla #3), `as_of`.
  El Protocol pasa a `quotes(requests) -> dict[key, Quote | QuoteError]`;
  `QuoteRequest.key` es una correlación opaca (el `security_id`) porque
  el ticker no es único entre plazas.
- Mapeo `(ticker, exchange)` → símbolo Yahoo. ⚠️ **La tabla del plan no
  era aplicable**: `{LSE, BME, XETRA, EPA, AMS, EBR, MIL, SWX, VIE, LIS}`
  son etiquetas coloquiales y **ninguna sobrevive a
  `catalog.venues.normalize_venue`** (`'LSE'` → `UNKNOWN` por tener 3
  caracteres; `'XETRA'` → `UNKNOWN` por tener 5). Escrita así no habría
  acertado una fila y toda posición europea habría caído en «sin mapeo»
  en silencio. Reescrita sobre el vocabulario real —las 4 etiquetas SEC y
  **MIC ISO 10383**: `XLON:'.L'`, `XMAD:'.MC'`, `XETR:'.DE'`,
  `XPAR:'.PA'`, `XAMS:'.AS'`, `XBRU:'.BR'`, `XLIS:'.LS'`, `XMIL`/`MTAA`,
  `XSWX`/`XVTX`, `XWBO`, `XCSE`, `XSTO`, `XHEL`, `XOSL`, `XFRA`—.
  Test de regresión que fija que las coloquiales NO son el vocabulario.
- **`UNKNOWN` → símbolo desnudo** (punto de parada (a), resuelto por el
  usuario el 2026-08-02). La SEC deja ~181 tickers sin plaza y tratarlos
  como «sin mapeo» los dejaría sin valorar siendo US cotizables. La red
  es D4: un europeo con `UNKNOWN` daría USD del proveedor ≠ EUR del
  catálogo → flag.
- Lectura por `fast_info` (`last_price`, `previous_close`, `currency`),
  los tres de una vez; NO se parsea `.info`. Throttling 1 req/s
  (`PRICE_THROTTLE_SECONDS`), serializado, cada lectura en
  `asyncio.to_thread` — **yfinance es síncrono** y bloquearía el event
  loop segundos.
- Normalización GBp/GBX→GBP (÷100, también `prev_close`), por cadena
  **exacta**: `'GBp'` y `'GBP'` se distinguen sólo por el *case*.
- **Hechos de la librería verificados con un probe en vivo** (lección
  44.6) contra KO/ULVR.L/IBE.MC/ALV.DE/MC.PA: (1) `fast_info` devuelve
  **`float`**, no `Decimal`; (2) Londres llega literalmente como `'GBp'`;
  (3) un símbolo inexistente lanza **`KeyError('exchangeTimezoneName')`**,
  no una excepción de red — un `except (HTTPError, ValueError)` no lo
  cazaría y se llevaría el lote; (4) `yf.Tickers` **no batchea**: cada
  `fast_info` dispara su petición perezosa, así que no se usa.
- **Salida**: 22 tests con monkeypatch (cero red) — US con conversión
  float→Decimal, LSE-peniques (÷100 y `'GBP'`), libras reales sin
  dividir, alias GBX, plaza sin mapeo sin gastar petición, `KeyError` sin
  tumbar el lote, fallo de red, precio 0, una entrada por `key`. Más 4 de
  integración: divisa del proveedor manda + flag de discrepancia +
  `pricing_enabled` con/sin key.
- **Bug D4 corregido de paso**: `refresh.py` persistía
  `Security.currency` junto a un precio de fuera. Ahora persiste la del
  proveedor, con `assert` que impide que una subunidad llegue a la
  columna, y el summary expone `quote_currency` + `currency_mismatch`
  (derivado de la fila persistida, no del refresco: si se derivara del
  refresco desaparecería en cuanto la quote entrase en TTL).

### 44.11.D — Refresco ✅ (2026-08-02)

- On-access y refresco manual comparten camino de código: sólo cambia
  `force`. Fallos parciales conservan la fila vieja (stale).
- `refresh_quotes` devuelve `RefreshOutcome(refreshed, errors)`: los
  motivos del intento ACTUAL alimentan el `exclusion_reason` de la
  posición. Funciona sin persistir el motivo porque una posición sin fila
  entra al lote en cada petición.
- FX en el mismo paso, con `quotes=` **explícito** (las divisas realmente en
  cartera) y llamado **antes** del trabajo transaccional, porque escribe.
- ⚠️ **`ensure_rates_for_dates` no bastaba.** Su canario da por buena cualquier
  tasa dentro de la ventana de fallback (14 días) y hace `continue` sin pedir
  nada. Medido contra la BD real el 2026-08-02 (última tasa a 15 días):
  convertir «ayer» resolvía con la del 18 de julio → **precio de hoy × tipo de
  hace dos semanas**. Decisión del usuario: la cartera exige tasa **exacta del
  día** y la pide (`missing_exact_rates` —añadida al servicio de `currency`,
  como manda la regla 3 del ADR— + `refresh_rates`). **La ventana de `currency`
  NO se toca**: es correcta para Finanzas Domésticas y cambiarla movería
  números de Deuda, Análisis y Dashboard. Best-effort: un domingo no hay tasa
  del BCE y se cae al fallback con su `fx_as_of` visible.
- 🔎 **Causa del hueco**: el cron de tasas está activo por defecto pero sólo
  dispara si el backend está vivo a esa hora, y esto no corre 24/7. Medido: 21
  fechas en dos años y medio, espaciadas ~15 días.
- Config: `PRICE_PROVIDER` default `yfinance`; Finnhub convive.
  `PRICE_THROTTLE_SECONDS` nuevo. Valor desconocido → **lanza**, no cae al
  default: arrancar con otro proveedor en silencio enmascara una errata de
  despliegue.
- `pricing_enabled` deja de significar «hay FINNHUB_API_KEY» y pasa a ser
  «el proveedor activo puede cotizar». El router tenía su propia copia del
  predicado; ahora hay una sola.

### 44.11.E — Valoración ✅ (2026-08-02)

- Alimentado el contrato: `market_value` (nativa) + `market_value_base`,
  `cost_basis_base`, `unrealized_pnl_base`, `fx_rate`, **`fx_as_of` =
  `ConversionResult.rate_date`**, `price_effect`/`fx_effect` **reales**,
  `weight_pct` calculado en base, `currency_exposure`, y totales
  `total_*_base`.
- Posición sin cotización o **sin tasa** → fuera de totales con
  `exclusion_reason` concreto.
- ⚠️ **Dato ficticio encontrado y corregido.** `fx_rate_at_trade` tenía
  `default=1` en el schema. Era inocuo mientras `fx_effect` salía siempre
  0; al cablear el FX vivo pasó a afirmar «compraste a 1 USD = 1 EUR» y la
  pantalla mostraba un efecto divisa que nadie introdujo. El único lote
  real del usuario (JNJ/USD, 2026-07-24) estaba exactamente así. Decisión
  del usuario: **derivar del BCE**. Ahora el campo es opcional (`None` =
  «no lo sé») y `portfolio.service.resolve_trade_fx` lo rellena con el
  tipo del BCE a la fecha de la operación; si el usuario lo declara, manda
  él (su bróker tiene el cambio real). Data-fix de lo anterior en
  `scripts/backfill_trade_fx.py` (dry-run por defecto) — script y no
  migración, por [PHASE-34].
- El coste en base va al tipo de la **fecha de compra**, no al de hoy:
  reexpresarlo a tipo de hoy escondería el efecto divisa entero. Hay un
  test que verifica que `price_effect + fx_effect == market_value_base −
  cost_basis_base`.
- `total_cost_basis` y `total_unrealized_pnl` (nativos) se conservan pero
  quedan documentados como sumas de divisas mezcladas: para agregar están
  los `_base`.

### 44.11.G — Smoke vivo ✅ ejecutado · ⏳ pendiente tu validación

`scripts/pricing_smoke.py` (fuera de CI), ejecutado el 2026-08-02:

| Símbolo | Precio | Divisa |
|---|---|---|
| KO | 87,589996 | USD |
| ULVR.L | **47,43** | **GBP** (÷100 desde 4743 GBp) |
| IBE.MC | 20,65 | EUR |
| ALV.DE | 432,50 | EUR |
| MC.PA | 475,15 | EUR |
| XYZ/XTKS | — | excluido, «plaza sin equivalencia» |

**Falta la validación del usuario contra su bróker** (no delegable).

---

## 2. Eliminado respecto al plan 44.8 original (y por qué)

| Sub-fase | Destino |
|---|---|
| A (migración `fx_rates` + modelos FX) | **Eliminada** — `price_quotes` ya existe con `currency`; FX = `exchange_rates` [D1] |
| C (adapter `ecb_fx.py`) | **Eliminada** — `currency/client.py` ya es ese cliente [D1] |
| F (`symbol_search`) | **Fuera de fase** — ADR-0008; se evalúa después en el slot del catálogo [D2] |

## 3. Verificación global

- [x] `pytest` verde; **cero red de verdad**: el bloqueo de `fetch_rates` vivía
      como fixture local en 2 ficheros y ahora es `autouse` en `conftest.py`.
      Al activarlo cayó un test que llevaba toda la fase en verde **porque
      salía a internet** — era la prueba de que el bloqueo faltaba.
- [x] Assert imposible persistir `GBp` + regresión LSE (÷100 y `'GBP'`).
- [x] Discrepancia divisa proveedor↔catálogo → flag visible (test de extremo a
      extremo, adapter → refresh → summary → UI).
- [x] Proveedor sin cobertura → 200 con exclusión estándar **y motivo**.
- [x] Proveedor caído → 200 con `quote_stale` marcado.
- [x] `fx_as_of` en el payload, con la fecha EFECTIVA (test con tasa de hace 3
      días que comprueba que NO se publica la de hoy).
- [x] Smoke ejecutado (5/5 mercados).
- [ ] **Contrastado con el bróker por el usuario** — pendiente, no delegable.
- [x] ADR de D1 mergeado antes que el código.
- [x] ruff · black · mypy 213 · docs-check · FE typecheck · lint · 133 web.
- [ ] `scripts/backfill_trade_fx.py --apply` sobre la BD real. Dry-run hecho:
      1 fila (lote JNJ del 2026-07-24, `1 → 0.87450809`). **Sin aplicar**:
      escribe en datos del usuario. Nota: la tasa sale del 2026-07-18
      (`previous`), no del 24 — conviene comprobar el cron de tasas.

## 4. Puntos de parada obligatoria

(a) Exchange en cartera sin sufijo en la tabla → preguntar, no inventar.
(b) Campo de `fast_info` sistemáticamente vacío/raro en un mercado →
documentar y preguntar. (c) Cualquier tentación de tocar `currency/` para
"adaptarlo" → parar: se consume tal cual; si de verdad falta algo, es
decisión de módulo transversal, no de esta fase.

## 5. Fuera de alcance

Valoración por múltiplos (→ **PHASE-44.12**, stub propio) ·
`symbol_search` (→ ADR-0008, fase posterior) · histórico de precios ·
websockets/tiempo real · scheduler propio · adapter EODHD (documentado,
no implementado) · retirar Finnhub.
