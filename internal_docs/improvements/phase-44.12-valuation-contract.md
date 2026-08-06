# PHASE-44.12 — Múltiplos de valoración · contrato de implementación

**Estado**: 📋 decisiones cerradas (usuario, 2026-08-06) — listo para implementar.
**Origen**: verificación adversarial de cinco definiciones (un refutador por
múltiplo + síntesis). Los 61 defectos encontrados están ya incorporados abajo.
**Precondición declarada en el stub**: precios de PHASE-44.11 validados por el
usuario contra su bróker (sub-fase G). **Sigue pendiente.**

## Decisiones del usuario (2026-08-06) — no reabrir

1. **Capitalización única** en los cinco múltiplos: `precio × shares_outstanding_eop`.
   El PER da 24,76× y no cuadra al 0,85% con el PER diluido de las webs
   financieras; se acepta a cambio de que «capitalización» signifique lo mismo
   en toda la pantalla.
2. **El hueco de detección de escala entre ~1,15× y ~800× queda declarado como
   limitación conocida.** No se baja el umbral de `validation._scale_coherence`:
   ningún emisor presenta en «unidades de 50», y cada falso positivo es una
   bandera roja que enseña a ignorar las banderas.
3. **El gate de pureza se cierra**: `test_el_engine_no_importa_io` pasa a
   prohibir también `app.modules.currency` y `app.modules.investment.pricing`.
4. **La cotización se pide al abrir** la pestaña. Quote caducada → se muestra
   con sello de caducidad, nunca bloquea.
5. **Financieras** (no preguntada, se da por buena): `per`/`price_book` limpios,
   `price_sales` con aviso ámbar, `price_fcf`/`ev_ebitda` negados. Sin ninguna
   financiera ingerida contra la que contrastarlo.

---

# Contrato único — PHASE-44.12 · Múltiplos de valoración

Verificado hoy contra la BD real (`crisol`, MCD `is_latest_view=t`) y contra el código en `C:/Users/membr/Desktop/Projects/TrackingFinance/backend/app/modules/investment/`. Todos los nombres de partida, helper y constante que aparecen abajo existen.

---

## 1. Tabla final

**Definición única de capitalización, común a los cinco:**
`capitalización = precio (en la divisa del estado) × shares_outstanding_eop`.
`shares_diluted` **no entra en ninguna fórmula** (es media ponderada del ejercicio, no un recuento a una fecha; y la nota de `canonical.py:356-361` —"ninguna métrica del catálogo la consume"— sigue siendo cierta, no hay que tocarla). Con eso, la palabra "capitalización" vale lo mismo en las cinco pantallas: 211.982.954.772,80 USD para MCD, no dos números.

| clave | etiqueta | unidad | fórmula (Amounts del engine) | partidas |
|---|---|---|---|---|
| `per` | PER — precio / beneficio | TIMES | `divide(market_cap, sourced(st,"net_income"), denominator_label="resultado neto", require_positive_denominator=True)` | `net_income`, `shares_outstanding_eop` |
| `price_sales` | Precio / ventas (P/S) | TIMES | `divide(market_cap, sourced(st,"revenue"), denominator_label="ventas", require_positive_denominator=True)` | `revenue`, `shares_outstanding_eop` |
| `price_book` | Precio / valor contable (P/VC) | TIMES | `divide(market_cap, sourced(st,"equity"), denominator_label="patrimonio neto", require_positive_denominator=True)` | `equity`, `shares_outstanding_eop` |
| `price_fcf` | Precio / caja libre (P/FCF) | TIMES | `divide(market_cap, dv.fcf_cfo(st), denominator_label="caja libre", require_positive_denominator=True)` | `cfo`, `capex`, `shares_outstanding_eop` |
| `ev_ebitda` | Valor de empresa / EBITDA | TIMES | `ev = add(market_cap, dv.net_debt(st))`; guarda `ev ≤ 0`; `divide(ev, dv.ebitda(st), denominator_label="EBITDA", require_positive_denominator=True)` | `short_term_debt`, `ltd_current_portion`, `long_term_debt`, `cash`, `current_financial_assets`, `ebit`, `depreciation_amortization`, `shares_outstanding_eop` |

**Acompañantes obligatorios en pantalla** (mismo módulo, mismo catálogo propio):

| clave | etiqueta | unidad | fórmula | por qué |
|---|---|---|---|---|
| `book_value_per_share` | Valor contable por acción | CURRENCY_PER_SHARE | `divide(equity, shares_outstanding_eop, denominator_label="acciones al cierre")` **sin** `require_positive` | No depende del precio: se emite aunque el P/VC se niegue. Aquí el negativo informa. |
| `fcf_yield` | Rentabilidad de la caja libre | PERCENT | `divide(fcf_cfo, market_cap, denominator_label="capitalización")` **sin** `require_positive` | Con FCF negativo dice "quema caja" sin invertir el orden. No es el recíproco del P/FCF. |
| `ev_sales` / `ev_fcf` | Contrastes de EV | TIMES | `divide(ev, revenue \| fcf_cfo, …, require_positive_denominator=True)` | Sin ellos, un P/S o un P/FCF de una empresa con 40.700 M$ de deuda neta se lee como si no la tuviera. Heredan procedencia `imputed_zero`. |
| `price_ffo` | Precio / FFO | TIMES | `divide(market_cap, dv.ffo(st), …, require_positive_denominator=True)` | **Sólo** si `is_reit`. Sustituye al P/FCF, no al EV/EBITDA. |

Derivaciones usadas (no son partidas canónicas; se citan con prefijo): `derivations.net_debt`, `derivations.total_debt`, `derivations.ebitda`, `derivations.fcf_cfo`, `derivations.ffo`.

---

## 2. Política común de casos límite

Tres definiciones distintas del mismo caso límite son un defecto de diseño. Una regla por caso, para los cinco:

1. **Denominador ≤ 0 → `require_positive_denominator=True`, siempre, en los cinco.**
   Gana `conventions.divide` (líneas 129-144) porque ya es la única guarda del resto del engine (R5 la usa con patrimonio medio negativo y su `not_computable` está persistido en el run de MCD). Ni `approximation` (mentiría: el número no está degradado, no existe), ni número negativo (se lee "baratísimo"), ni cero. Los acompañantes no la llevan porque su denominador es capitalización o recuento de acciones, magnitudes que no pueden ser negativas: la regla es homogénea — *todo denominador que pueda cambiar de signo lleva el guard*.

2. **Numerador ≤ 0: sólo existe en EV, y se intercepta ANTES de dividir.**
   `divide` no mira el numerador. Patrón ya establecido por `S5 _years_to_repay` (`base_ratios.py:798-821`), que corta con `net_debt < 0` y devuelve razón propia. Con caja neta > capitalización, `ev_ebitda` sale `not_computable` nombrando capitalización y deuda neta.

3. **Escala de acciones: se LEE, no se re-deriva.**
   La ingesta ya normaliza `shares_basic`/`shares_diluted` **usando `shares_outstanding_eop` como testigo** (`normalization.py:362-419`) y deja la traza en `raw_source_ref['scale_corrections']`; la validación ya emite bandera roja `scale_mismatch:*` en `quality_flags`. Por tanto: (a) si hay `scale_corrections` con `rule='shares_scale'` → `Flag(info)` citando factor, testigo y antes→después; (b) si hay un `quality_flag` cuya clave empieza por `scale_mismatch:` → `not_computable` **reutilizando su mensaje**. **Cero guardas numéricas propias**: cualquier cruce eop/basic que escribamos sale ≈1 por construcción (en MCD hoy: 0,99579) y sería una segunda definición de "escala rota" que divergiría de la de aguas arriba — [PHASE-38].

4. **Serie vacía**: `series.latest` es `CanonicalStatement | None` (`types.py:79-80`). Primera línea de cada múltiplo: `if st is None → not_computable("no hay ningún ejercicio ingerido para este valor")`. Sin esto es `AttributeError`, y el contrato del engine prohíbe la excepción.

5. **Partición pura / impura.** Función pura en `analysis/engine/valuation.py`, firma `(series, *, price: Decimal, quote_as_of: date, ingestion_flags)`. Todo el IO —`pricing.service.quote_security` (que **commitea**, `pricing/service.py:186-212`), `currency.service.convert`, la resolución de divisa— vive en `analysis/service.py`. Motivo: el gate `test_el_engine_no_importa_io` prohíbe `sqlalchemy` en `engine/*.py`, y un múltiplo con `db` dentro rompería la promesa de "engine testeable con sintéticos".

6. **Divisa y FX.** `quote.currency is None` (el proveedor no la declara, caso Finnhub) y distinta de la del estado → `not_computable`. Si difiere: `convert(amount=Decimal(1), …)` para obtener la **tasa**, y `if fx.fallback == "missing" → not_computable("no hay tipo X→Y para el <fecha>")`. Esto no es opcional: `convert` **no lanza**, devuelve `rate=1` y el importe sin convertir (`currency/service.py:127-131`). La normalización de subunidades (GBp/GBX) **no se replica aquí**: es responsabilidad del adapter (regla 2 de `pricing/adapters/base.py:55`; `yfinance.py:98-105` ya divide por 100). Una sola definición del predicado.

7. **Sin cotización / cotización caduca.** `quote is None` o `QuoteError` → `not_computable` con el `reason` del proveedor **tal cual** (está escrito para el usuario). Quote más vieja que el TTL → se calcula igual con `quote_stale=true` visible. Nunca se sustituye por el coste de la posición.

8. **Doble staleness (guardarraíl 3 del stub, no reabrible).** Siempre en el payload: `quote_as_of`, `quote_stale`, `fiscal_year_end`, `days_since_fye = quote.as_of.date() − fiscal_year_end`. Cortes: se **importan** `synthesis.STALENESS_FRESH_DAYS (274)` y `STALENESS_STALE_DAYS (548)` (no se copian los literales), declarando por escrito que se toman prestados. ≥274 → `Flag(info)`; ≥548 → `Flag(amber)`. **Nunca bloquea**: el número sigue siendo verdad.

9. **Por tipo de valor.** `ETF` → los cinco `not_computable` ("un fondo cotizado no tiene cuenta de resultados propia"). `ADR` → `not_computable` ("es un ADR y no consta cuántas ordinarias representa"). `is_financial` → `per` y `price_book` se calculan (el P/VC es *el* múltiplo bancario); `price_sales` se calcula con `Flag(amber)` ("en una financiera 'Ventas' es ingreso bruto por intereses y comisiones"); `price_fcf` y `ev_ebitda` se **niegan con razón propia** ("en una entidad financiera la deuda es materia prima del negocio: la deuda neta no significa nada y el valor de empresa no se puede formar"). **No se reutiliza el literal `forensic.NOT_APPLICABLE_TO_FINANCIALS`**: EV/EBITDA no es un modelo, y compartir el texto hace que editarlo allí cambie la razón aquí en silencio. La clave nunca se omite.

10. **Sin banda, y fuera del catálogo del engine.** Catálogo propio `valuation.VALUATION_METRICS` con `label` + `unit`, expuesto por API, **no sumado** a `catalog.ALL_METRIC_DEFINITIONS`. Razón mecánica, no estética: `ALL_METRIC_KEYS` alimenta la huella de forma del engine (subir `ENGINE_VERSION` por una métrica que no va en ningún run sería declarar falsamente que la matemática book-based cambió), `thresholds_from` sembraría filas en `scoring_thresholds` con cortes que nadie ha calibrado, y hay asserts de recuento en 57. `to_metric_result(key, fy, amount, thresholds={})` ya deja `band=None` sin código nuevo (`metrics.py:121-131`). Y con `label`+`unit` publicados, la web no repite la regresión de 44.9 (un margen leído como "0,42").

11. **Ningún umbral inventado.** Se retiran los ">100×" y los "<15× barato". El único aviso de nivel permitido sale de los propios datos del sistema: **denominador atípico** — si el denominador del último ejercicio < 0,5 × mediana de la serie (`conventions.median`) → `Flag(info)` "ejercicio atípico: el múltiplo lo domina el denominador". Se permite reutilizar cortes **ya calibrados** citando su origen: `R7 < 0,03` (`base_ratios.py:212-221`) → aviso de materialidad en `price_fcf`. Cualquier otro corte se etiqueta explícitamente "decisión de presentación".

12. **Procedencia y notas escritas a mano.** El precio entra como `Amount(value=…, provenance=Provenance.SOURCED)`, no `constant()` — son idénticos byte a byte (`conventions.py:51-53`), pero el nombre "constante" despista al lector; lo que informa de verdad es el payload (`rate`, `rate_date`, `fallback`). La procedencia degradada viaja sola hasta la pantalla (en MCD, `imputed_zero` por `current_financial_assets` en todo lo que toca `net_debt`). Ninguna nota afirma un hecho sin comprobarlo: la nota "EBITDA = EBIT reportado + D&A" **sólo se imprime si `st.provenance_of("ebit") is Provenance.SOURCED`**; si el EBIT viene derivado (pretax + gasto financiero, el caso normal según `canonical.py:334-343`), `Flag(info)` diciendo que ese EBITDA no es el de mercado. Igual con las no recurrentes del PER: `impairments` y `gains_on_sale_of_business` están en `IMPUTABLE_ZERO_ITEMS`, así que si alguna es `imputed_zero` el aviso es "no se ha podido comprobar del todo: el filing no publica <partida>", nunca "no hubo deterioros".

13. **Fechas: se declaran, no se comprueban.** El múltiplo mezcla tres: precio de hoy, recuento de portada (`dei:EntityCommonStockSharesOutstanding`, posterior al cierre, y su fecha exacta **no se persiste**) y balance a `fiscal_year_end`. Se publican las que hay y se declara la que falta. **No se construye guarda de splits sobre `inv_corporate_actions`**: verificado, tiene `user_id NOT NULL` — es el libro de la cartera del usuario, no un catálogo global; dos usuarios obtendrían veredictos distintos para el mismo valor.

---

## 3. Qué vería el usuario para MCD hoy

Datos reales (FY2025, cierre 2025-12-31, USD): `revenue` 26.885 M$ · `net_income` 8.563 M$ · `equity` **−1.791 M$** · `cfo` 10.551 M$ · `capex` 3.365 M$ · `ebit` 12.393 M$ (sourced, `us-gaap:OperatingIncomeLoss`) · `D&A` 457 M$ · deuda 798 + 725 + 39.973 M$ · `cash` 774 M$ · `current_financial_assets` 0 (imputed_zero) · `shares_outstanding_eop` **710.398.642**.
Con precio **298,40 USD**: capitalización **211.982.954.772,80 USD**; deuda neta 40.722 M$; EV **252.704.954.772,80 USD**; EBITDA 12.850 M$; caja libre 7.186 M$.

| clave | resultado | lo que lee el usuario |
|---|---|---|
| `per` | **24,76×** (ok) | — |
| `price_sales` | **7,88×** (ok) | — |
| `price_book` | **not_computable** | "El patrimonio neto de 2025 es negativo (−1.791 M$), así que un múltiplo sobre valor contable no existe aquí. No es una señal de quiebra: procede de la autocartera acumulada (79.316 M$) frente a reservas de 70.282 M$, es decir de años de recompras, no de pérdidas." |
| `book_value_per_share` | **−2,52 USD/acción** | Se emite igualmente. Aviso: el recuento es el de portada del filing y el patrimonio es a 31/12/2025 — no son la misma fecha. |
| `price_fcf` | **29,50×** (ok) · `fcf_yield` **3,39%** | — |
| `ev_ebitda` | **19,67×** (ok, procedencia `imputed_zero`) | Aviso permanente: el valor de empresa no incluye intereses minoritarios ni acciones preferentes (no están entre las 49 partidas) mientras el EBITDA consolida el 100%. |
| `ev_sales` / `ev_fcf` | **9,40×** / **35,17×** (`imputed_zero`) | El salto frente a 7,88× y 29,50× es exactamente la deuda neta de 40.722 M$ que la capitalización sola no ve. |

Banderas que se levantan hoy:
- `info` — "La ingesta reescaló los recuentos medios de acciones por 1.000.000 contra el recuento de portada (713,4 → 713.400.000; 716,4 → 716.400.000)." Es traza auditable de la corrección, no una alarma.
- `info` — "No se ha podido comprobar del todo si el resultado incluye partidas no recurrentes: el filing no publica deterioros." (`impairments` es `imputed_zero`; `gains_on_sale_of_business` = 149 M$ sourced, por debajo del 10% del beneficio.)
- `info` — "El cuadre del balance no es verificable" (ya persistida por la ingesta).
- **Frescura: sin bandera.** 2025-12-31 → hoy = **218 días**, por debajo de los 274. Cruza el umbral el 1 de octubre de 2026 sin que nadie toque nada.
- Sin aviso de denominador atípico: beneficio 104% de la mediana de la serie, caja libre 101%, R7 = 26,7% (muy por encima del 0,03).

**Salvedad que hay que decir en voz alta:** con la base tal y como está, los cinco saldrían hoy `not_computable` — "sin cotización de MCD". `price_quotes` tiene **una sola fila** y es de JNJ (253,94 USD, yfinance, 2026-08-04). Los 298,40 USD son el precio supuesto del enunciado, no un dato del sistema.

---

## 4. Decisiones abiertas (necesitan al usuario)

1. **PER: capitalización o BPA diluido.** El contrato usa `shares_outstanding_eop` (24,76×). El PER que publican las webs financieras usa acciones diluidas medias (24,96×). Divergencia 0,85%. ¿Acepta esa diferencia a cambio de que "capitalización" signifique lo mismo en las cinco pantallas, o prefiere el PER diluido clásico **renombrado** ("PER diluido = precio / BPA diluido") y declarando por qué no cuadra con la capitalización?
2. **Hueco de escala entre ~1,15× y ~800×.** Ni `normalization` (sólo actúa con potencias de 10 y exponente ≥3) ni `validation` (alarma en 1000×) tocan ese rango. La valoración **no** lo va a cubrir (sería una segunda definición). ¿Se deja declarado como limitación conocida, o se baja el umbral **aguas arriba** en `validation._scale_coherence` (una sola definición, pero cambia la ingesta)?
3. **Financieras.** Propuesta: `per`/`price_book` limpios, `price_sales` con aviso ámbar, `price_fcf`/`ev_ebitda` negados. ¿Conforme? Es política de producto, no matemática — y no hay ninguna financiera ingerida contra la que contrastarlo.
4. **Gate de pureza.** Hoy `test_el_engine_no_importa_io` prohíbe `sqlalchemy`/`httpx`/… pero **no** `app.modules.currency` ni `app.modules.investment.pricing`, cuya raíz es `app` y pasa limpia. La partición pura/impura de la regla 5 dependería de la disciplina, no del gate. ¿Autoriza añadir esas dos raíces a `prohibidos` (es tocar un test existente)?
5. **Refresco del precio.** `quote_security` **commitea** la sesión (ADR-0009). ¿Se refresca al abrir la pestaña de Análisis, o hace falta un botón explícito? Y con la quote caducada por TTL: ¿se muestra con sello de caducidad (propuesta) o se bloquea?

---

## 5. Riesgos que ningún test detectaría

- **Error de escala de modo común.** Si los tres recuentos vienen mal por el mismo factor, todo cuadra entre sí y la capitalización sale 10⁶ veces mal. No hay testigo absoluto: entre las 49 partidas **no existe ninguna de BPA** (el pipeline descarta los ratios por acción), así que nada puede desmentirlo. Los múltiplos saldrían absurdos, pero un test con hechos sintéticos coherentes nunca lo ve.
- **Multiclase** (GOOGL/GOOG, BRK.A/B): los hechos `dei` se colapsan y no hay metadato de clase. La capitalización sale mal por un factor plausible — no llama la atención de nadie.
- **Split entre el cierre y hoy.** El recuento es anterior al precio y no hay catálogo global de acciones corporativas. Un 2:1 deja el múltiplo al doble, y el número resultante sigue siendo creíble.
- **Adapters futuros que no normalicen subunidades.** yfinance ya divide GBp por 100; el siguiente proveedor puede no hacerlo. El múltiplo saldría 100× y "100×" no es imposible: nadie lo distingue de una empresa cara.
- **Minoritarios y preferentes.** El EV compra sólo la matriz, el EBITDA consolida el 100%: en grupos con minoritarios relevantes el EV/EBITDA sale **sistemáticamente bajo** y se lee como barato. Es un sesgo, no un fallo: ningún assert lo captura.
- **Notas escritas a mano que caducan.** Es la séptima aparición del mecanismo de `lessons.md`. La nota "EBIT reportado" es verdad en MCD y falsa en cuanto llegue un emisor con `ebit` derivado; por eso el contrato la condiciona a `provenance_of("ebit")`. Cualquier otra nota que se escriba a mano tiene el mismo destino.
- **Fuera del run, fuera de la huella.** Al no persistirse, ningún golden test cubre estas fórmulas: se puede cambiar una y no romper nada. Si se quiere gate, hay que crear uno propio del módulo de valoración (huella de forma de `VALUATION_METRICS`) — no vale el de `ENGINE_VERSION`.
- **`quote_security` commitea.** Llamada en mitad de una unidad de trabajo, confirma a medias. Un test unitario del engine puro jamás la ejecuta.
- **El universo de prueba es de dos valores, ambos USD/NYSE/STOCK/no-financiera/no-REIT.** Las rutas de FX (`fallback == "missing"`), ETF, ADR, financiera y socimi están razonadas sobre código y **no observadas ni una vez**. Una suite verde con MCD y JNJ no dice nada sobre ellas.

*Verificado sin ejecutar tests y sin editar ningún fichero; sólo lecturas de código y SELECT sobre `crisol`. La aritmética se reprodujo con `Decimal` en `backend/.venv/Scripts/python.exe`, no a través de las primitivas reales del engine.*