# PHASE-44.13 — Buscador E2, paridad móvil del informe y el cron de tasas que llevaba mudo desde PHASE-11.1

**Estado**: ✅ código completo y verde · ⏳ pendiente prueba manual del usuario
**Rama**: `main` (push directo, convención del proyecto)
**Fecha**: 2026-08-07

## Objetivo

Cerrar la deuda declarada del módulo Inversión en tres frentes que el usuario
eligió a la vez: los cabos sueltos de PHASE-44.11/44.12, la Entrega 2 del
buscador (PHASE-44.8) y la paridad móvil del informe de análisis (PHASE-44.9).

---

## 1. El cron de tasas: dos defectos independientes, ninguno visible

Se entró a esto por una nota de una línea en el checkpoint de 44.11 —«la tasa
sale del 2026-07-18, no del 24; conviene comprobar el cron»— y resultó que **el
cron nocturno de divisas no traía nada desde que se construyó en PHASE-11.1**.

### Defecto 1 — el canario laxo

`refresh_currency_rates_job` llamaba a `ensure_rates_for_dates([ayer, hoy])`, que
usa como canario `get_rate_with_fallback`: acepta **cualquier tasa de los 14 días
anteriores** y hace `continue` sin pedir nada. Consecuencia: el día que entraba
una tasa, el job se callaba durante dos semanas.

La huella estaba en la BD del usuario, y es inconfundible:

```
2026-04-01 → 04-16 (15d) → 05-01 (15d) → 05-18 (17d) → 06-02 (15d) → 06-18 (16d) → 07-18
```

Una fecha cada ~15 días — el ancho exacto de la ventana de fallback. **23 fechas
distintas en meses de uso.** Y las dos últimas (04 y 06 de agosto) traían **1
sola divisa** en lugar de 9: son las peticiones que la cartera se hacía por su
cuenta desde PHASE-44.11, con la política estricta que ya había tenido que
inventarse para sí misma.

### Defecto 2 — el timeout

Arreglado el canario, el job seguía cojo. Medido contra la API el mismo día:

| Petición | Tiempo | Con timeout de 10 s |
|---|---|---|
| Fecha histórica (`2026-07-24`) | 17,0 s | falla |
| Fecha histórica (`2026-07-23`) | 13,7 s | falla |
| Ayer, 9 divisas | 10,3 s | **falla** |
| Hoy, 9 divisas | 9,3 s | pasa por 0,7 s |

O sea que el cron habría traído la mitad, y con mal día ninguna. Hacían falta
los dos arreglos para que el job sirviera de algo.

### Lo que se hizo

- `currency.service.ensure_exact_rates_for_dates` — hermana **estricta** de
  `ensure_rates_for_dates`, con `missing_exact_rates` como canario. La política
  laxa **no se toca**: es la correcta para rellenar fechas pasadas (50 fechas
  serían 50 round-trips) y cambiarla movería números de Deuda, Análisis y
  Dashboard.
- `settings.frankfurter_background_timeout_seconds = 45`, sólo para el camino de
  fondo. El global de 10 s se queda: ahí hay un usuario esperando en
  `/portfolio/summary`.
- `pricing/service._ensure_fx_rates_for_currencies` deja de tener su copia del
  predicado y consume la compartida (lección [PHASE-38]: una sola definición).

### Datos del usuario corregidos

- Rellenadas las tasas de `2026-07-24` (viernes hábil), `08-06` y `08-07`.
- `scripts/backfill_trade_fx.py --apply`: el lote de JNJ pasa de `fx=1` a
  **`0.87896634`**, con `fallback=exact` de la fecha de la compra. Con la tabla
  como estaba habría escrito `0.87450809` (la del sábado 18) — medio punto
  porcentual de diferencia en el coste base de la posición. Segunda pasada: 0
  filas (idempotente).

### Dos bugs del propio script, que nunca se había ejecutado con `--apply`

1. `UnicodeEncodeError` al imprimir el informe: el `→` no existe en cp1252, la
   codificación por defecto de la consola de Windows. Pasado a ASCII.
2. `NoReferencedTableError` en el `commit`: `inv_lots` tiene FK a `accounts` y a
   `users`, y sin esos modelos registrados en el metadata el flush revienta. El
   dry-run no lo destapaba —hace un `SELECT` con el join explícito, que no
   necesita resolver la FK—, así que el script estaba probado sólo por la mitad.

---

## 2. Buscador — Entrega 2 (PHASE-44.8)

Buscar «Macdonald» daba cero; sólo funcionaba el ticker exacto o el nombre
literal de la SEC.

### El índice

`catalog/symbol_index.py` carga el parquet empaquetado con `edgartools`:
**10.365 emisores, 7.992 CIKs, 0,3 s, sin red** (verificado con el sandbox de red
activo, que es el criterio de aceptación «buscar con DNS bloqueado devuelve
resultados»).

**Dos trampas de la librería, las dos encontradas ejecutándola** (lección
[PHASE-44.6]):

1. `get_company_tickers(as_dataframe=False)` devuelve la tabla **sin la columna
   `exchange`**, pese a que su docstring la promete. Con esa vía todas las plazas
   habrían salido `UNKNOWN` en silencio, y con ellas el desempate NYSE > OTC que
   decide qué fila representa a cada emisor.
2. Los 224 `exchange` nulos llegan como `float('nan')`, no como `None`. Pasarlos
   por `str()` da `'NAN'`, que `normalize_venue` aceptaría como MIC de tres
   letras.

Antes de eso, un tercer callejón: el plan apuntaba a un parquet de 291 KB, pero
`get_company_dataset()` exige una **descarga de 500 MB** de submissions. La
función correcta era otra.

### El ranking (`catalog/ranking.py`, PURO)

Tres reglas, todas salidas de mirar el fichero real y no de la intuición:

1. **El colapso es por CIK**, no por `(ticker, plaza)`. `Banco Santander, S.A.`
   está como `SAN`/NYSE y `BCDRF`/OTC con el mismo cik 891478; Santander UK sale
   dos veces (`SNTUF`, `STNDF`) y Polska otras dos. Sin colapsar, «santander»
   devuelve 8 filas de las que 3 son duplicados.
2. **La subcadena de nombre sólo vale desde 4 caracteres.** `ITX` es subcadena de
   `ADITXT`, así que un `LIKE %itx%` le da `ADTX · Aditxt, Inc.` a quien busca
   Inditex.
3. **El fuzzy va contra los TOKENS**, no contra el nombre entero. La SEC escribe
   `MCDONALDS CORP` sin apóstrofo, y comparar `MACDONALD` con el nombre completo
   no pasa del umbral por culpa del ` CORP`. Contra el vocabulario de tokens sí,
   en 0 ms.

Resultados medidos: `coca`→KO primero · `santander`→SAN sin duplicados ·
`itx`→sin ADTX · `MC`→Moelis · `Macdonald`→**MCD**.

### La identidad: `listing_key` opaca

El cliente deja de mandar plaza. Manda la clave que le dio el buscador
(`cat:<uuid>` · `idx:<PLAZA>:<TICKER>` · `typed:<TICKER>`) y el servidor la
vuelve a resolver. Lo que no se envía no se puede inventar.

Lo que aporta sobre `/resolve`: la plaza real. Resolviendo por ticker suelto, MCD
entraba en el catálogo como `UNKNOWN`; con `idx:NYSE:MCD`, como `NYSE`.

### Un bug que cazó un test

La deduplicación entre capas **nunca casaba**: el catálogo guarda el CIK como
`'0000063908'` y el índice lo trae como `63908`. McDonald's salía dos veces —el
duplicado exacto que este buscador existe para evitar—. De ahí `normalize_cik`,
aplicado en toda comparación de identidad.

### Avisos honestos

Verificado uno a uno contra el índice: `ITX`, `IBE`, `NESN` y `BMW` **no están**;
`VOO`, `VTI`, `IVV` y `SCHD` tampoco (los ETF de estructura abierta no tienen
CIK, a diferencia de los trusts, que sí: SPY, QQQ). Pero `SAP`, `ASML` y `SAN`
**sí** están como ADR, y `MC`, `OR` y `AIR` están siendo otra empresa (Moelis, OR
Royalties, AAR Corp). Avisar de «no existe» sobre una consulta que devuelve
resultados sería mentir en la otra dirección, así que el mapa de avisos sólo
lleva ausencias comprobadas.

---

## 3. Paridad móvil del informe

El móvil se había quedado en la vista resumida de PHASE-44.7 mientras la web
pasaba a seis pestañas: pintaba `[...red_signals, ...amber_signals].join(' · ')`
—o sea las **claves crudas** del motor, `B4_dividend_funded_externally` en
pantalla— y los valores sin formato por unidad (un margen del 42 % como `0,42`).
Son exactamente los defectos que PHASE-44.9 arregló en web.

### La decisión: mover la capa pura, no duplicarla

Escribir el informe otra vez para RN habría creado dos implementaciones de lo
mismo, que es cómo se llega a que dos pantallas de la misma app cuenten cosas
distintas. Se movió a `packages/ui` todo lo que es cálculo y contenido:

| Fichero | Qué |
|---|---|
| `investment-metric-format.ts` | formato por unidad, cortes, importes (+ sus 13 tests) |
| `investment-metric-index.ts` | índices de métricas y catálogo, `collectRunMetrics` |
| `investment-metric-rows.ts` | construcción de filas con banda, corte y motivo |
| `investment-matrix.ts` | `MatrixRow`/`MatrixCell` + `bandColors`/`bandLabel` |
| `investment-statement-rows.ts` | filas de los estados, marcas de procedencia, calidad |
| `investment-flags.ts` | `groupFlags` (dedup de banderas repetidas) |
| `investment-report-sections.ts` | qué métricas por bloque, con sus notas, y las 6 pestañas |

Lo único que queda propio de cada app es el renderizado. `packages/ui` gana
`@crisol/types` como dependencia: es acíclico (types no tiene deps internas) y
ADR-0001 prohíbe **componentes** en ese paquete, no funciones puras.

Efecto colateral verificado: web sigue verde con las mismas pantallas, y ahora
`RATIO_FAMILIES`, `FORENSIC_KEYS`, `DIVIDEND_BLOCKS` y las claves de pestaña
(`veredicto`, `estados`…) tienen **una** definición.

### Lo que el móvil tiene ahora

Buscador con las dos capas y adopción por `listing_key` · hero persistente con
dictamen, confianza y ejercicios · las **siete pestañas** (Estados con selector
balance/resultados/flujos, Ratios por familia, Evolución con serie y variación,
Forense, Dividendo, Valoración y Veredicto) · matriz concepto × ejercicio con la
columna del concepto fija fuera del scroll horizontal · señales con etiqueta,
valor, banda, corte y motivo de las que no puntúan · banderas agrupadas.

### Un fallo propio, cazado al revisar el alcance

Al centralizar la lista de pestañas en `REPORT_TABS` escribí **seis** — las de
PHASE-44.9— olvidando que 44.12 había añadido Valoración. Como el mismo commit
cableaba `TAB_IDS = REPORT_TABS.map(...)` en la web, el botón «Valoración» seguía
pintándose pero al pulsarlo `?tab=valoracion` fallaba el `includes` y caía al
veredicto: **la pestaña quedaba inalcanzable**. Corregido, y con ella el móvil
gana también su vista de múltiplos (con el doble staleness y el semáforo del
proveedor, sin bandas: sin comparables de sector un color sería una opinión).

Es exactamente el riesgo de centralizar una lista: la copia nueva se escribe de
memoria y nadie compara con la vieja. La contramedida barata habría sido derivar
la lista del código existente en vez de teclearla — y es lo que se hizo con las
claves (`estados`, `veredicto`…), que sí se tomaron del fichero real.

---

## Archivos clave

- `backend/app/modules/currency/service.py` — `ensure_exact_rates_for_dates`
- `backend/app/core/scheduler.py` — el cron, con su timeout
- `backend/app/modules/investment/catalog/symbol_index.py` — índice en memoria
- `backend/app/modules/investment/catalog/ranking.py` — relevancia y colapso
- `backend/app/modules/investment/catalog/listing_key.py` — clave opaca, `normalize_cik`
- `packages/ui/src/investment-*.ts` — la capa pura compartida
- `apps/mobile/components/investment/` — `report-tabs.tsx`, `year-matrix.tsx`, `security-search.tsx`

## Endpoints

- `GET /investment/securities/search` — ahora por capas; `q` sube a `min_length=2`;
  la respuesta gana `listing_key`, `source`, `cik`, `exchange_label`,
  `analysis_reason`, `index_ready` y `notice`.
- `POST /investment/securities/adopt` — **nuevo**. 201 · 404 si la SEC no
  reconoce el ticker · 422 con motivo si la clave está mal formada · 503 sin
  `EDGAR_IDENTITY`.

## Migraciones

Ninguna.

## Verificación

- Backend: **1251 passed** (suite completa, 12 min) · ruff · black · mypy 217 ficheros.
- Frontend: typecheck · lint · knip limpio · **242 tests** (web 125 · móvil 23 ·
  services 60 · ui 31 · store 3).
- Los tests nuevos: 27 de ranking e índice (uno llama a la librería REAL), 9 de
  búsqueda por capas y adopción, 8 de las dos políticas de frescura de tasas, 5
  del buscador web, 5 de las pestañas de móvil.
- El test de regresión del cron se comprobó **rompiéndolo a propósito**: con la
  llamada laxa restaurada, caen 2 tests. Un gate que nunca falla no es un gate.

## Limitaciones conocidas

- **Prueba manual pendiente** (la del usuario, y la de precios contra su bróker
  de 44.11, que no es delegable).
- El móvil muestra los estados en importe; los modos «% común» y «Δ%» de la web
  no tienen selector todavía (la capa compartida ya los soporta).
- La pestaña de móvil vive en estado local, no en la URL: Expo Router no tiene
  aquí el query param de la web. Las claves sí son las mismas.
- Entregas 3 (combobox rico con teclado), 4 y 5 (proveedor multi-mercado) del
  buscador siguen pendientes.
- `q=santander` deja SAN en 3.ª posición (los tres empatan a puntuación y
  desempata el ticker alfabéticamente). Cumple el criterio del plan («top 3»)
  pero es mejorable.

## Próxima fase

Sin decidir. Candidatos: E3 del buscador, o la valoración por múltiplos en móvil.
