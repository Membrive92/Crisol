# ADR-0009 — `exchange_rates` es la única fuente de tipos de cambio, y `currency` es un módulo transversal

**Estado**: aceptada
**Fecha**: 2026-08-02
**Fase**: PHASE-44.11 (sub-fase 44.11.0 — bloquea el resto del plan
[`improvements/phase-44.11-pricing-quotes-fx.md`](../improvements/phase-44.11-pricing-quotes-fx.md);
el contraste plan-vs-repo que la origina está en
[`improvements/phase-44.11-pricing-decisiones.md`](../improvements/phase-44.11-pricing-decisiones.md),
Decisión 1)
**Sustituye a**: la tabla `fx_rates` y el adapter `pricing/adapters/ecb_fx.py`
que describía `improvements/ARCHITECTURE-investment-module.md` §4 (ya corregido
en el mismo commit).

---

## Contexto

El plan original de pricing del módulo de Inversión pedía tres piezas nuevas:
una tabla `fx_rates (date, pair, rate, source)`, un adapter `ecb_fx.py` contra
la API de Frankfurter y un `ensure_rates(pairs, as_of)` que resolviera el último
día hábil.

Las tres existen desde PHASE-8.1, y el cron que las alimenta desde PHASE-11.1:

| Lo que pedía el plan | Lo que ya hay |
|---|---|
| tabla `fx_rates` | `exchange_rates` — PK `(rate_date, base, quote)`, `rate NUMERIC(20,8)`, `source`, `fetched_at` |
| adapter contra Frankfurter (datos del BCE) | `currency/client.py` |
| `ensure_rates(pairs, as_of)` | `currency.service.ensure_rates_for_dates(...)` |
| «último día hábil ≤ as_of» | `_resolve_eur_rate` → `(rate, rate_date, fallback)` |
| `fx_as_of` en el payload | `ConversionResult.rate_date` |
| conversión vía EUR | `currency.service.convert(...)`, con redondeo por divisa (JPY de 0 decimales incluido) |

El obstáculo era de fronteras, no de código: `architecture.md` §6 dice que
**distintos módulos de dominio no se importan entre sí**, y `investment` tirando
de `currency` parecía cruzar esa línea.

**La frontera no está donde parecía.** `currency/` no vive dentro de
`personal_finance/`: es *top-level*, hermano de `auth/`, `users/` y `ai/`. Lo
que ocurre es que §6 enumera los transversales **por extensión** —`auth`,
`users`, `ai`— y esa lista se escribió antes de que `currency` existiera, así
que el documento se podía leer de las dos maneras. Mientras tanto
`personal_finance` ya lo importa desde **siete** sitios (`accounts/debt_health.py`,
`accounts/debt_history.py`, `accounts/service.py`, `analytics/service.py`,
`dashboard/conversion.py`, `dashboard/service.py`, `debt/service.py`), más
`core/scheduler.py` para el cron. El precedente estaba establecido de facto y
sin declarar.

El riesgo de la alternativa es conocido en este proyecto: **dos tablas de tipos
son dos fuentes de verdad**. El cron llenaría una y el módulo de inversión la
otra, y el día que Frankfurter respondiera distinto en dos momentos del día, la
pantalla de Deuda y la de Cartera convertirían el mismo importe a números
distintos sin que nadie pudiera decir cuál creer. Es la lección [PHASE-34]
(«cuando parcheas la misma raíz ≥2 veces, mueve la fuente de verdad») y la
[PHASE-37] (MUX por entidad, porque sumar dos fuentes para la misma cosa
reintroduce el doble conteo).

## Decisión

1. **`exchange_rates` es la única fuente de tipos de cambio de la aplicación.**
   Queda prohibido crear otra tabla, otro cliente FX u otro cron de tasas en
   cualquier módulo. La sub-fase A (migración `fx_rates`) y la C (adapter
   `ecb_fx.py`) del plan original desaparecen: cero migraciones, cero
   dependencias nuevas por FX.

2. **`currency/` es un módulo transversal**, en la misma categoría que `auth/`,
   `users/` y `ai/`: cualquier módulo de dominio puede consumirlo. `architecture.md`
   §6 se corrige en el mismo commit para decirlo por su nombre en vez de dejarlo
   a interpretación.

3. **Se consume por `currency.service`, nunca por debajo.** Los módulos de
   dominio llaman a `convert(...)`, `ensure_rates_for_dates(...)`,
   `missing_exact_rates(...)` o `refresh_rates(...)`. Importar
   `currency.models.ExchangeRate`, `currency.repository` o `currency.client`
   desde un módulo de dominio no está permitido: si hace falta una query que el
   servicio no expone, **se añade al servicio** (así nació
   `missing_exact_rates`, ver punto 6).

4. **`fallback="missing"` no se silencia jamás.** `convert()` no lanza cuando no
   hay tasa: devuelve `rate=Decimal("1")` y **el importe sin convertir**, y deja
   la señalización a quien llama. Para una cartera eso significa que unos
   dólares se sumarían a los euros como si fueran euros —un error del orden del
   8 % que no se ve—. En `investment`, `fallback == "missing"` degrada la
   posición a la **exclusión estándar**: fuera de totales, con su motivo visible,
   exactamente igual que una posición sin cotización. Valorar a coste o sumar
   sin convertir como sustituto silencioso está prohibido.

5. **El `rate_date` aplicado viaja al payload** como `fx_as_of`. Una conversión
   con la tasa del viernes sobre un precio del lunes tiene que poder decirlo.

6. **La frescura exigible la decide cada consumidor, no la fuente.** Convertir
   una transacción PASADA y valorar una cartera HOY tienen necesidades
   distintas, y la política de `currency` sólo servía a la primera:
   `ensure_rates_for_dates` da por buena cualquier tasa dentro de la ventana de
   fallback (14 días) y no pide nada. Verificado contra la BD real el
   2026-08-02, con la última tasa a 15 días: convertir «ayer» resolvía con la
   del 18 de julio, así que la cartera habría mostrado **precio de hoy × tipo de
   hace dos semanas** sin intentar actualizarlo.

   El módulo de inversión exige tasa **exacta del día** y la pide si falta
   (`missing_exact_rates` + `refresh_rates`). **No se cambia la ventana de
   `currency`**: es correcta para lo que hace Finanzas Domésticas, y tocarla
   movería números de Deuda, Análisis y Dashboard sin demostrar equivalencia
   ([PHASE-41]). Es best-effort: el BCE no publica fines de semana, así que «no
   hay tasa de hoy» es lo normal un domingo y se cae al fallback con su
   `fx_as_of` visible.

## Consecuencias

**A favor**

- Un solo número por divisa y día en toda la aplicación: Deuda, Análisis y
  Cartera convierten igual por construcción, no por disciplina.
- El módulo de Inversión hereda gratis el cron nocturno, el snapshot offline
  sembrado (arranque sin red), el fallback al último día hábil, la re-ancla de
  cross-rates de AUDIT-2026-05 y el redondeo por divisa.
- PHASE-44.11 se queda **sin migraciones y sin tablas nuevas**. El trabajo real
  se concentra donde estaba el valor: el adapter de cotizaciones.

**En contra, y asumido**

- `investment` pasa a depender de un módulo que no controla. Se acepta porque la
  alternativa —aislamiento por copia— es precisamente la que produce las dos
  fuentes de verdad.
- El vocabulario de divisas cubierto por defecto lo fija `currency`, no
  `investment` (ver deuda declarada).

## Deuda declarada

- **`ensure_rates_for_dates` hace `commit()` por dentro** (uno por fecha
  fetcheada). No es un detalle de estilo: llamarlo en mitad de una unidad de
  trabajo del módulo de inversión confirmaría escrituras a medias. Se llama
  **antes** de abrir el trabajo transaccional del refresco de precios, nunca
  entremedias.

- **`COMMON_QUOTES` es el vocabulario por defecto**, y hoy son nueve: USD, GBP,
  JPY, CHF, CAD, AUD, MXN, BRL, CNY. Cubre la tabla de sufijos de mercado de
  PHASE-44.11 (LSE, BME, XETRA, Euronext, SWX), pero una posición en una divisa
  fuera de esa tupla caería al `fallback="missing"` del punto 4 —correcto, pero
  silencioso desde el punto de vista del operador—. `investment` pasa `quotes=`
  **explícito** con las divisas realmente presentes en la cartera en vez de
  confiarse del default.

- **El cron de tasas no llena la tabla en una app local.** `enable_currency_cron`
  está activo por defecto, pero sólo dispara si el backend está vivo a esa hora,
  y esto no corre 24/7. Medido el 2026-08-02: **21 fechas** en dos años y medio,
  espaciadas ~15 días — el patrón de `ensure_rates_for_dates` rellenando bajo
  demanda, no el de un cron nocturno. No es un bug que se arregle con código; es
  la razón por la que el punto 6 no puede confiarse al cron.

- **`dashboard/conversion.py:40` importa `ExchangeRate` directamente**, saltándose
  la regla 3. Es anterior a este ADR y no se toca aquí (cambiarlo movería números
  del core de Finanzas Domésticas, que es justo lo que [PHASE-41] prohíbe hacer
  de paso). Queda anotado como la única excepción conocida: la regla 3 no lo
  legitima, y quien vuelva a tocar ese fichero debería subirlo al servicio.
