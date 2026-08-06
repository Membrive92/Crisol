# PHASE-44.11 — Precios de activos: decisiones antes de implementar

> Complemento a [`phase-44.11-pricing-plan-original.md`](phase-44.11-pricing-plan-original.md)
> (el plan del usuario, escrito como «44.8» antes de la Decisión 6; renombrado
> para no colisionar con la PHASE-44.8 real, el buscador). El plan **vigente**,
> ya con las seis decisiones integradas, es
> [`phase-44.11-pricing-quotes-fx.md`](phase-44.11-pricing-quotes-fx.md). Este documento **no cambia el plan**: recoge lo que hay
> que decidir antes de tocar código, con la evidencia de cada caso y una
> propuesta. Escrito el 2026-08-01, tras contrastar el plan contra el estado real
> del repo.
>
> **Nada de esto está implementado todavía.** Las seis decisiones están abiertas.

---

## Resumen ejecutivo

El plan está bien construido, pero da por incierto el estado del repo en cosas
que **ya existen**, y propone construir de cero una pieza —el FX del BCE— que el
proyecto lleva usando desde PHASE-8.1. Contrastado fichero a fichero:

| Sub-fase del plan | Estado real |
|---|---|
| **A** — esquema y modelos | `price_quotes` ✅ existe con su migración y **ya tiene `currency`**. `fx_rates` ❌ no existe… pero ver Decisión 1 |
| **B** — adapter yfinance | ❌ por hacer. Es el grueso real del trabajo |
| **C** — FX del BCE | ⚠️ **ya existe entero** en `modules/currency/` (ver Decisión 1) |
| **D** — política de refresco | ✅ el esqueleto existe (`refresh.py`, TTL en config); falta el batch y el cableado del FX |
| **E** — integración en la valoración | ✅ el **contrato** ya está: `market_value`, `price_effect`, `fx_effect`, `quote_stale`, `weight_pct`… todos declarados y hoy sin alimentar |
| **F** — `symbol_search` | ⚠️ **choca con el ADR-0008** (ver Decisión 2) |
| **G** — smoke vivo | ❌ por hacer |

El trabajo real, si se aceptan las propuestas, se concentra en **B, D, E y G**.

---

## Decisión 1 — El FX: ¿tabla nueva o la que ya existe?

**La más importante de las seis.**

### Lo que el plan propone

Una tabla `fx_rates (date, pair, rate, source)` nueva, más un adapter
`pricing/adapters/ecb_fx.py` que hable con la API de Frankfurter, más un
`ensure_rates(pairs, as_of)` que resuelva el último día hábil.

### Lo que ya hay en el repo

Desde PHASE-8.1, y en producción:

| Lo que pide el plan | Lo que existe |
|---|---|
| tabla `fx_rates` | **`exchange_rates`** — PK `(rate_date, base, quote)`, `rate NUMERIC(20,8)`, `source`, `fetched_at` |
| «Frankfurter sirve los datos del BCE, JSON, sin key» | **`currency/client.py`** — cliente async, y su docstring dice casi esa misma frase |
| `ensure_rates(pairs, as_of)` | **`currency.service.ensure_rates_for_dates(...)`** |
| «último día hábil ≤ as_of» | **`_resolve_eur_rate`** devuelve `(rate, rate_date, fallback)` |
| `fx_as_of` en el payload | **`ConversionResult.rate_date`** — el dato ya viaja |
| conversión vía EUR | **`currency.service.convert(...)`**, con redondeo por divisa (JPY de 0 decimales incluido) |

Y además: un **cron nocturno** (PHASE-11.1) que rellena la tabla, y un snapshot
offline sembrado para arrancar sin red.

### El obstáculo real

`architecture.md` §6 dice que **distintos módulos de dominio no se importan entre
sí**. `investment` tirando de `currency` parece cruzar esa frontera.

**Pero la frontera no está donde parece.** Verificado:

- `currency/` **no está dentro de `personal_finance/`**: es un módulo
  *top-level*, hermano de `auth`, `users` y `ai` — los transversales que
  cualquiera puede consumir.
- `personal_finance` **ya lo importa desde cinco sitios**
  (`accounts/debt_health.py`, `accounts/debt_history.py`, `accounts/service.py`,
  `analytics/service.py`, `dashboard/conversion.py`).
- El índice de docs describe las tasas como *«datos públicos globales»*, no como
  datos de finanzas personales.

O sea: `currency` **ya es de facto un servicio transversal**, y el precedente de
consumirlo desde un módulo de dominio está establecido.

### El riesgo de la tabla nueva

Dos tablas de tipos de cambio son **dos fuentes de verdad**. El cron llena una y
el módulo de inversión la otra; el día que Frankfurter devuelva algo distinto en
dos momentos del día, la pantalla de Deuda y la de Cartera convertirán el mismo
importe a números distintos y **nadie sabrá cuál creer**.

Este proyecto ya se ha quemado con eso: [PHASE-34] («cuando parcheas la misma
raíz ≥2 veces, mueve la fuente de verdad») y [PHASE-37] (el MUX por pasivo,
porque sumar dos fuentes para la misma entidad reintroducía el doble conteo).

### 📌 Propuesta

**Reutilizar `exchange_rates` vía `currency.service`. No crear `fx_rates`.**

Consecuencias: desaparece la sub-fase A, desaparece la sub-fase C, cero
migraciones, cero adapter del BCE. Y se cierra con un **ADR corto** que declare
`exchange_rates` como la única fuente de tipos de la aplicación y a `currency`
como servicio transversal (aclarando `architecture.md` §6, que hoy se puede leer
de las dos maneras).

**Si prefieres tabla propia**: es defendible por aislamiento del módulo, pero
entonces el ADR debe decir **cuál manda cuando discrepen** y la UI debe poder
explicar por qué dos pantallas dan números distintos.

---

## Decisión 2 — `symbol_search`: ¿dentro o fuera?

### El choque

El plan lo pide en el Protocol (§44.8.B) y le dedica la sub-fase F entera. Pero
**se retiró hace una semana** en PHASE-44.8 E1, y el motivo está escrito en
`pricing/adapters/base.py`:

> 1. El `/search` de Finnhub **no devuelve la bolsa**: sus cuatro campos son
>    `description`, `displaySymbol`, `symbol` y `type`, así que la implementación
>    rellenaba `exchange` con un ticker de visualización. Un buscador
>    multi-mercado sin mercado.
> 2. Buscar un símbolo **no es responsabilidad del proveedor de precios**. Se
>    separa en su propio contrato, `catalog/adapters/symbol_search/`.

Eso está fijado en el [ADR-0008](../decisions/0008-investment-symbol-search.md).

### Lo que cambia respecto a entonces

El motivo (1) era específico de **Finnhub**. yfinance sí trae bolsa, así que la
objeción técnica desaparece. La objeción (2) —de diseño— sigue en pie.

### 📌 Propuesta

**Dejar F fuera de esta fase.** Hacer A–E y G.

Si yfinance resulta buena fuente de búsqueda, entra **después** como
`SymbolSearchAdapter` en `catalog/adapters/symbol_search/`, que es donde el
ADR-0008 dice que vive esa decisión. Y ahí tiene un premio: sería una alternativa
a **Twelve Data** sin su problema de licencia (su ToS prohíbe cachear y el uso
comercial del plan gratis), que es una de las decisiones que llevas abiertas
desde julio.

Meterlo en `PriceAdapter` ahora significaría deshacer un ADR de hace una semana
para volver a hacerlo bien más tarde.

---

## Decisión 3 — ¿yfinance sustituye a Finnhub, o conviven?

El plan llama a yfinance «adapter primario» pero no dice qué pasa con el adapter
de Finnhub, que existe y está probado.

Datos: `PRICE_PROVIDER` ya es un selector en config, y `FINNHUB_API_KEY` está
vacía, así que **hoy el pricing está apagado de todas formas**.

### 📌 Propuesta

**Conviven detrás del selector; el default pasa a `yfinance`.** Cuesta cero
—`factory.py` ya está preparado para elegir— y te deja volver atrás cambiando una
variable de entorno si yfinance se rompe (es no oficial, y el plan ya absorbe ese
riesgo con el diseño *staleness-tolerant*).

Retirarlo tampoco sería grave, pero no gana nada.

---

## Decisión 4 — La divisa del quote: un bug latente que hay que arreglar igual

**No es una decisión, es un aviso**: el plan lo arregla sin darse cuenta de que
el problema ya existe.

Hoy, `refresh.py:56` persiste la cotización con `currency=target.currency`, o sea
**la divisa que dice el `Security` del catálogo**, no la que devuelve el
proveedor. El `Quote` del Protocol ni siquiera tiene campo de divisa.

Para valores de EE. UU. da igual. Pero es exactamente lo que rompe la **regla
dura nº 2** del plan («nunca se persiste `GBp`»): si un valor de la Bolsa de
Londres está catalogado como `GBP` y el proveedor devuelve peniques, se
persistirían peniques etiquetados como libras — y el valor de mercado saldría
**100 veces mayor**.

### 📌 Propuesta

Meter `currency` en el dataclass `Quote` (el plan ya lo hace) y persistir **la
del proveedor**, no la del catálogo. Añadir el assert de `GBp` que pide el plan.
Y un test de regresión con una posición de LSE.

---

## Decisión 5 — Esto desbloquea la hoja 10 del cuaderno. ¿La hacemos?

**La consecuencia que el plan no menciona, y probablemente la más valiosa.**

En PHASE-44.9 se aplazó la pestaña de **Valoración** —PER, precio/ventas,
precio/valor contable, precio/FCF, EV/EBITDA y el descuento de dividendos de
Gordon— por una razón concreta: *el motor no recibe precio*. Y no había fuente,
porque `FINNHUB_API_KEY` está vacía.

**Con yfinance eso deja de ser cierto**: es gratis y sin key. Y las magnitudes
que faltaban ya están todas en el canónico:

| Múltiplo | Qué necesita | ¿Se puede? |
|---|---|---|
| PER | precio × acciones / resultado neto | ✅ |
| Precio / ventas | idem / ventas | ✅ |
| Precio / valor contable | idem / patrimonio neto | ✅ |
| Precio / caja libre | idem / FCF | ✅ |
| EV / EBITDA | (capitalización + deuda − caja) / EBITDA | ✅ (`net_debt` ya existe) |
| Gordon | dividendo, crecimiento, **beta y prima de riesgo** | ❌ falta beta |
| Comparación **vs sector** | múltiplos de comparables | ❌ no hay fuente |

**La restricción arquitectónica se mantiene** y no es negociable: tiene que vivir
**fuera del `AnalysisRun`**. El motor forense es book-based a propósito —*«un
score que se mueve con la cotización no sería reproducible al reejecutar un run
antiguo»*, `forensic.py:3-6`— así que la valoración sería una capa aparte que
cruza cotización viva × último estado financiero, calculada al vuelo y no
persistida en el run.

### 📌 Propuesta

**No meterla en esta fase.** Primero que los precios funcionen y los valides
contra tu bróker (sub-fase G). Pero anotarla ya como fase siguiente, porque pasa
de «imposible» a «a tiro» y es lo que cierra tu cuaderno.

---

## Decisión 6 — Numeración

El plan se titula PHASE-44.8, pero esa fase existe y está en `main` (buscador
local-first, Entrega 1 de 5). Vamos por 44.10.

### 📌 Propuesta

Renumerar a **PHASE-44.11**. Trivial, pero si no se hace ahora quedan dos
documentos distintos llamados 44.8 y dentro de tres meses nadie sabrá cuál es
cuál — que es justo el tipo de podredumbre que `docs-check` no puede detectar.

---

## Lo que NO hay que decidir (el plan ya lo cierra bien)

- Adapter primario yfinance, con EODHD documentado como canje de pago.
- Prohibido: scraping HTML, websockets, histórico de precios, cron/scheduler.
- `PRICE_TTL_HOURS=24` configurable a 1; refresco **on-access** + manual.
- Fallo del proveedor → se sirve la última cotización guardada y se marca
  *stale*; nunca se bloquea la cartera.
- Posición sin cotización → fuera de los totales, con su motivo. **Jamás valorar
  a coste como sustituto silencioso.**
- Cero llamadas de red en CI; verificación viva por script de smoke.
- Los tres puntos de parada obligatoria del §4.

Todo eso es sólido y coherente con cómo está construido el resto del módulo.

---

## Si se aceptan las seis propuestas

El trabajo queda en:

1. **B** — adapter yfinance: mapeo `(ticker, exchange)` → símbolo Yahoo, lectura
   por `fast_info`, normalización de peniques, batch con throttling, errores por
   símbolo sin tumbar el lote.
2. **D** — refresco: batch on-access con TTL + refresco manual, asegurando los
   tipos vía `currency.service`.
3. **E** — valoración: alimentar el contrato que ya existe, con conversión y
   `rate_date` propagado.
4. **G** — smoke vivo contra cinco mercados + validación tuya contra el bróker.

Más un **ADR** por la Decisión 1 y, si la aceptas, la corrección de la Decisión 4.

Sin migraciones. Sin tablas nuevas. Sin dependencias nuevas salvo `yfinance`.
