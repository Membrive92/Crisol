# PHASE-44.8 — Buscador de valores híbrido (plan de implementación)

**Estado**: 🚧 Entrega 1 implementada y verde (2026-07-26, sin commitear).
La columna `analysis_status` y su evidencia se **adelantaron de la Entrega 2**:
cerrar el callejón de SPY sin ella habría exigido negarse a crear el `Security`,
lo que rompía el caso legítimo de llevar SPY en cartera. Lo que queda de la E2 es
el índice en memoria de la SEC, el ranking y `POST /adopt`.
**Origen**: petición del usuario — «el buscador busca por ticker en EDGAR y es
confuso; que autocomplete con resultados de varios mercados como el de
Interactive Brokers»
**Prerrequisito duro**: PHASE-44.7 commiteada (prueba manual pendiente). Sólo la
Entrega 1 puede entrar dentro de 44.7; las Entregas 2-5 son 44.8.

---

## 0. La idea en una frase

El buscador consulta **en local** el catálogo más un índice de los ~10.400
emisores que conoce la SEC, y **sólo en la pestaña Cartera** amplía a un
proveedor externo multi-mercado bajo demanda; cada fila pinta símbolo · nombre ·
bolsa · divisa · tipo y declara **antes del clic** si es analizable, sólo cartera
o pendiente de comprobar.

La partición no es una preferencia estética: **el motor forense sólo funciona con
filers de la SEC** (necesita XBRL US-GAAP), así que ofrecer multi-mercado en
Análisis es prometer algo que el engine no puede cumplir. En Cartera, en cambio,
registrar una posición en Inditex sólo necesita coste y divisa — y esa maquinaria
ya existe.

---

## 1. Diagnóstico — cinco defectos, ninguno de ellos «faltan mercados»

1. **El cliente inventa el mercado.** `apps/web/components/investment/security-search.tsx:38`
   manda `exchange: 'US'` fijo al resolver el ticker tecleado, contra la
   restricción única `uq_securities_ticker_exchange` de
   `backend/app/modules/investment/catalog/models.py`. El móvil hace lo mismo.
   Consecuencia: el mismo emisor puede entrar dos veces (`MCD/US` y `MCD/NYSE`),
   con dos ingestas, dos `AnalysisRun` y los lotes de cartera repartidos entre
   dos ids.
2. **`resolve` fija la identidad a martillazos.** `catalog/service.py:60-72`
   escribe `currency="USD"` y `accounting_std=GAAP` para todo lo que entra,
   incluidos los ADR extranjeros.
3. **La regla de «es analizable» está escrita dos veces** — en
   `catalog/schemas.py` (`analysis_available` como `cik is not None`) y otra vez a
   mano al construir el hit en `catalog/router.py` — y **es falsa**: SPY (CIK
   884394) y QQQ (CIK 1067839) tienen CIK. Hoy saldrían como acciones ordinarias
   analizables y el engine ingeriría los filings de un *unit investment trust*.
4. **Una petición por pulsación.** `packages/services/src/query/hooks/useInvestment.ts:21-29`
   no tiene debounce ni `placeholderData` y arranca en `length >= 1`: teclear
   `MCDONALDS` son 9 peticiones y la lista parpadea. Además la key
   `queryKeys.investment.search(q)` desciende de `investment.all`
   (`packages/services/src/query/keys.ts:185`), así que cualquier invalidación del
   módulo — por ejemplo al adoptar el valor recién elegido — refetchea la propia
   búsqueda.
5. **Un 500 donde el router promete un 404.** La excepción de
   `CompanyNotFoundError` de la librería no está traducida, pese a que el
   docstring de `resolve_endpoint` documenta el 404.

`external_search_available` es hoy un literal `False` en el router, y
`SecuritySearchHit` tiene 6 campos: no hay divisa, ni MIC, ni tipo de
instrumento. La fila que pide el usuario no se puede pintar con el contrato
actual.

---

## 2. Decisiones de diseño (y la trampa que motiva cada una)

### 2.1. El mercado lo pone el servidor: `listing_key` opaco

El cliente deja de mandar `exchange`. Manda una **clave opaca** que el servidor
sabe re-resolver:

```
cat:<uuid>                    → ya está en el catálogo
idx:<VENUE>:<TICKER>          → del índice SEC
ext:<PROVIDER>:<MIC>:<TICKER> → del proveedor externo (sólo Cartera)
typed:<TICKER>                → escotilla: resolver contra EDGAR
```

Es el movimiento de PHASE-34 aplicado al mercado: cambiar **dónde vive la
verdad** en vez de añadir otro guardarraíl sobre la fuente equivocada. Un cliente
no puede inyectar una divisa o un MIC inventados porque no los envía.

### 2.2. Vocabulario de `exchange` (String(16)) — controlado, sin MIC fabricado

| Origen | Valor almacenado |
|---|---|
| Índice SEC | `NYSE` · `NASDAQ` · `OTC` · `CBOE` · `UNKNOWN` (la etiqueta de la SEC normalizada a mayúsculas) |
| Proveedor externo | El **MIC ISO 10383 real** que da el proveedor (`XMAD`, `XAMS`, `XETR`…) |

Verificado que las mayúsculas son lo correcto: los tests actuales persisten
`NYSE` (`backend/tests/test_investment_catalog.py:118`, y el `_normalize` del
schema ya sube a mayúsculas el `nyse` de la línea 97). **No** se fabrica un MIC
para las filas de la SEC: su fichero no lo trae, y adivinarlo (¿XNYS o XNGS?)
sería inventar un dato.

Esto resuelve además la colisión de tickers entre mercados: `MC` es Moelis en
`NYSE` y LVMH en `XPAR`; `AIR` es AAR Corp en `NYSE` y Airbus en `XPAR`. Con el
vocabulario anterior (`'US'` para todo) esas dos parejas colisionaban en la
restricción única.

### 2.3. La capacidad es un tri-estado con evidencia, no un `cik IS NOT NULL`

Nueva columna `securities.analysis_status`, escrita **al adoptar** y
**recalculada en cada ingesta**:

| Valor | Significado | Ejemplo verificado |
|---|---|---|
| `ok` | Hay 10-K con taxonomía us-gaap | MCD |
| `no_annual` | Tiene CIK pero no presenta 10-K | SPY, QQQ (son trusts) |
| `non_gaap` | Presenta 20-F con `ifrs-full` contra un `concept_map` us-gaap | SAN, ASML, SAP |
| `not_supported` | Sin CIK (listing no-US) | Inditex vía proveedor externo |
| `unknown` | Aún no comprobado | fila recién vista en el índice |

**Por qué una columna y no derivarlo**: la distinción `no_annual` vs `non_gaap`
exige contar filings, o sea red. No se puede calcular dentro de un `/search` que
debe responder sin salir de la máquina.

**Por qué NO se toca `accounting_std` para avisar**: verificado que sería un
no-op numérico. `thresholds/seed.py` genera las filas de **todos** los
`AccountingStd` con los mismos cortes; lo único que cambia es
`model_variant=UNCALIBRATED`. Marcar SAN como IFRS no evita que se le apliquen
los cutoffs de Beneish y Altman calibrados en US-GAAP — sólo cambia la etiqueta.
Y peor: `accounting_std` alimenta el `thresholds_hash`, así que mover el valor
cambiaría el `thresholds_version` de los runs ya guardados. El aviso va en
`analysis_status` y en el badge; la norma contable se queda como está.

### 2.4. Dedupe por CIK, no por (ticker, MIC)

Un CIK tiene varios tickers: 10.429 tickers para 8.018 CIKs, 1.458 CIKs con más
de uno (Alphabet aparece cuatro veces: GOOGL, GOOG, GOOGM, GOOGN). Y las OTC
duplican emisores enteros: `santander` devuelve dos pares de filas que son la
**misma** entidad (Santander UK como SNTUF y STNDF; Santander Polska como BKZHF y
BKZHY).

El colapso se hace **por CIK**, quedándose con la línea de mayor prominencia de
plaza (NYSE > NASDAQ > CBOE > OTC). Colapsar por `(ticker, MIC)` no valdría:
las filas legacy del catálogo llevan `exchange='US'` y el índice dirá `NYSE`, así
que el par no coincide y el mismo emisor saldría dos veces — pulsando la segunda
se crearía un `Security` duplicado, que es justo el daño que este plan viene a
evitar.

**Orden obligatorio**: el script de normalización de las filas legacy corre
**antes** de habilitar el índice, no después.

### 2.5. El proveedor externo vive detrás de un adapter y está apagado por defecto

Mismo patrón que `FundamentalsAdapter` y `PriceAdapter`. Un `SymbolSearchAdapter`
con su factory; `settings.investment_symbol_provider` por defecto `"none"`
(convención ya existente en `backend/app/core/config.py:134-135`, donde
`price_provider` y `finnhub_api_key` hacen lo propio).

Consecuencias de aislarlo así:
- Cambiar mañana de proveedor (Twelve Data gratis → EODHD comercial) es el
  adapter, ~100 líneas, sin tocar la UI ni el resto del backend.
- Con `none` el módulo funciona **entero** sin red: el índice SEC es local.
- **Nada del proveedor se persiste.** Caché LRU **en memoria** con TTL de 300 s
  y tope de 256 entradas, keyed por query normalizada. Es el mecanismo que
  mantiene el uso dentro de lo que permite su licencia (su ToS §2.3(g) prohíbe
  cachear más allá de lo documentado y §16.2(a) obliga a borrar en 30 días), y
  por eso **no** se descarga su volcado de 250.000 instrumentos a Postgres.

---

## 3. Modelo de datos — una migración, una columna

```python
# backend/alembic/versions/<rev>_investment_analysis_status.py
# down_revision: tomarlo de `alembic heads` (UNA sola línea) y NUNCA de
# `ls versions | tail` — los revision id son aleatorios, no secuenciales
# (lección PHASE-44.1).
def upgrade() -> None:
    op.add_column(
        "securities",
        sa.Column("analysis_status", sa.String(16), nullable=True),
    )

def downgrade() -> None:
    op.drop_column("securities", "analysis_status")
```

`String(16)` nullable y **no** un enum nativo: el conjunto de estados va a
crecer (un `ALTER TYPE ADD VALUE` no es reversible en un `downgrade` limpio).

**Lo que NO se añade, y por qué:**

- **No** columna `mic`: `exchange` ya es `String(16)` y aloja el MIC de las filas
  externas (§2.2).
- **No** tabla de listings ni de índice: el índice vive **en memoria**
  (`functools.lru_cache` + `asyncio.to_thread`), 291 KB de parquet. Una tabla
  obligaría a un seed, a un cron y a mantener la sincronía con la SEC.
- **No** extensión `pg_trgm`: el filtrado es en Python sobre el índice en
  memoria, así que la relevancia es determinista y testeable sin BD.
- **No** cron: `ARCHITECTURE-investment-module.md` rechaza explícitamente el
  scheduler para este módulo. El refresco del índice, si se hace, es perezoso y
  bajo demanda.

---

## 4. Fuentes de datos (todo verificado golpeándolas, 2026-07-25)

| Fuente | Qué aporta | Key | Licencia | Uso aquí |
|---|---|---|---|---|
| **Parquet de `edgartools`** | 10.365 emisores con CIK, ticker, nombre, plaza. 291 KB, **offline** | No | Dominio público (SEC) | Índice base, capa 2 |
| **`company_tickers_exchange.json` (SEC)** | 10.412 filas, campos `cik, name, ticker, exchange` | No (UA identificativo obligatorio: 403 sin él) | Dominio público | Refresco opcional del índice |
| **Twelve Data `/symbol_search`** | `symbol, instrument_name, exchange, mic_code, currency, country, instrument_type` — 86 MICs | No (indocumentado) | **Restrictiva**: prohíbe caché persistente y uso comercial del free tier | Capa 3, sólo Cartera, sólo en memoria |
| **OpenFIGI `/v3/mapping`** | Resolución precisa por `(ticker, micCode)`, 25 req/min | No | **Dominio público**, redistribuible | Plan B / enriquecido futuro |
| **Finnhub** | `/stock/symbol` trae `mic` + `currency` | Sí | — | Descartado: `/search` sólo da 4 campos y no incluye bolsa |

Lo que el índice SEC **no** cubre, verificado y que la UI debe decir por su
nombre: Inditex (`ITX`), Iberdrola (`IBE`), BMW y Nestlé (`NESN`) **no existen**
en el fichero; los emisores extranjeros sólo entran por su ADR estadounidense
(SAN→NYSE, ASML→NASDAQ, SAP→NYSE). Y los ETF de estructura abierta tampoco:
`VOO`, `VTI`, `IVV`, `SCHD` → 0 filas, mientras `SPY`, `QQQ`, `GLD`, `DIA` sí
están (son trusts con CIK).

---

## 5. Backend

### 5.1. Ficheros nuevos

Todos en `backend/app/modules/investment/catalog/`:

| Fichero | Contenido | Pureza |
|---|---|---|
| `capabilities.py` | `CapabilityState`, `CapabilitySet`, `capabilities_for(security_or_hit)`, `selectable_for(intent, caps)` — **fuente única** de la regla | PURO (candidato al test de pureza por AST del engine) |
| `venues.py` | `normalize_venue(raw) -> str`, etiqueta humana y `rank` de prominencia. No fabrica MIC | PURO |
| `ranking.py` | `relevance_score(row, q)`, `collapse_by_cik(rows)`, `ALIASES` | PURO |
| `symbol_index.py` | Único fichero que conoce la fuente del índice: `load_index()`, `search_index(q, limit)`, `index_ready()`. El `import pandas` va **dentro** de la función | I/O aislado |
| `adapters/symbol_search/base.py` | `ExternalListing` (frozen) + `SymbolSearchAdapter` (Protocol) | Contrato |
| `adapters/symbol_search/twelvedata.py` | Implementación + mapeo `instrument_type` → `SecurityType` + filtro de ruido | I/O |
| `adapters/symbol_search/factory.py` | `get_symbol_search_adapter()` → `None` si `provider == "none"` | — |
| `scripts/probe_twelvedata.py` | Imprime `repr` y tipo de **cada** campo antes de mapear nada | — |
| `scripts/normalize_security_exchanges.py` | `'US'` → plaza real, idempotente, aborta si el destino ya existe | — |

### 5.2. Endpoints

```python
GET /securities/search?q=<str>&intent=analysis|portfolio&limit=<int>
# q: min_length=2. Capa 1 (catálogo) + capa 2 (índice en memoria) siempre.
# Capa 3 (externa) SÓLO si intent=portfolio, el provider está activo y len(q)>=3.
# `/search` sigue declarándose ANTES de `/{security_id}`: si no, FastAPI parsea
# "search" como UUID → 422 (trampa ya documentada en el propio router).
# Presupuesto de la capa 3: 1,5 s. Timeout o error → resultados locales +
# external.status='unavailable'. NUNCA un 500.

POST /securities/adopt   {"listing_key": "<clave opaca>"}
# Crea (o devuelve) el Security. Re-resuelve la clave en servidor.
# Para `idx:` y `typed:` pasa por EDGAR → CIK, SIC, is_financial, is_reit,
# y persiste analysis_status contando los 10-K.
# Para `ext:` NO pasa por EDGAR: cik=NULL, exchange=MIC, currency y
# security_type del proveedor, accounting_std=IFRS (descriptivo; el análisis
# lo bloquea analysis_status='not_supported', así que ese valor no se usa),
# sector=UNKNOWN.

POST /securities/resolve   # deprecated=True, se conserva
# Los tests de 44.7 y el móvil legacy lo usan. Deja de aceptar el `exchange`
# del cliente: toma la plaza de la identidad. Efecto colateral deseado: el móvil
# deja de poder crear una fila paralela sin tocar `apps/mobile`.
```

**Por qué `adopt` para `idx:` pasa siempre por EDGAR**: sin la llamada no hay
SIC, y sin SIC un banco entraría con `is_financial=False` y **los ocho scores
forenses correrían sobre una financiera**, que es exactamente lo que la regla
dura del engine prohíbe.

### 5.3. Ficheros editados

| Fichero | Cambio |
|---|---|
| `catalog/schemas.py` | `SecuritySearchHit` de 6 a 12 campos (§6.1); `SecurityCapabilities`; `SecurityAdoptRequest`; `SecuritySearchResponse` gana `groups`, `index_ready`, `external`; `SecurityResponse.analysis_available` **delega** en `capabilities_for` |
| `catalog/router.py` | `intent`, `q` a `min_length=2`, deja de construir el hit a mano (mata la regla duplicada), `POST /adopt`, traduce `CompanyNotFoundError` → 404 |
| `catalog/service.py` | `search_layered()`, `adopt_listing()`; `resolve_security` deja de escribir `USD`/`GAAP` a pelo |
| `catalog/repository.py` | `search_securities` también por CIK y prefijo de nombre; la ordenación sale de SQL y pasa a `ranking.py` |
| `fundamentals/adapters/edgar.py` | FIX del 500; `SecurityIdentity` gana `venues` y `annual_report_count` |
| `fundamentals/service.py`, `analysis/service.py` | Sus guardas usan `capabilities_for` y su `reason`; sin CIK → **422 con motivo**, no «lanza la ingesta primero» para algo cuya ingesta no puede funcionar |
| `pricing/adapters/base.py`, `finnhub.py` | Borrar `symbol_search` (su `/search` no devuelve bolsa; `finnhub.py:66` mapea `exchange=displaySymbol`, que es un ticker) |
| `core/config.py` | `investment_symbol_provider: str = "none"` |

### 5.4. Degradación (explícita, nunca un error opaco)

| Situación | Comportamiento |
|---|---|
| Sin red | Capas 1 y 2 funcionan. Es la prueba de aceptación: buscar con **DNS bloqueado** debe devolver resultados |
| `EDGAR_IDENTITY` sin configurar | Las filas del índice salen **no seleccionables** con badge «Falta configuración», no un 503 tras el clic |
| Provider externo apagado | `external.enabled=false`; el grupo externo no se pinta |
| Provider caído o lento | Resultados locales + `external.status='unavailable'` con aviso en el pie |
| Ticker deslistado | 404 con motivo «ya no cotiza / la SEC no lo reconoce» |

---

## 6. Frontend

### 6.1. La fila

```
┌──────────────────────────────────────────────────────────────────────┐
│  Buscar valor:  santa|                                               │
├──────────────────────────────────────────────────────────────────────┤
│  EN TU CATÁLOGO                                                      │
│  MCD    McDonald's Corporation        NYSE   USD  Acción  ✓Analizable│
├──────────────────────────────────────────────────────────────────────┤
│  MERCADOS US (SEC)                                                   │
│  SAN    Banco Santander, S.A.         NYSE   USD  ADR    ⚠ IFRS      │
│  BSAC   Banco Santander-Chile         NYSE   USD  ADR    ⚠ IFRS      │
│  SNTUF  Santander UK plc              OTC    USD  ADR    ? Comprobar │
├──────────────────────────────────────────────────────────────────────┤
│  OTROS MERCADOS            (sólo cartera · vía Twelve Data)          │
│  SAN    Banco Santander, S.A.  Madrid XMAD   EUR  Acción  ○Sólo cartera│
│  BNC    Banco Santander        LSE    XLON   GBp  Acción  ○Sólo cartera│
├──────────────────────────────────────────────────────────────────────┤
│  + Añadir a mano otro mercado          · Buscar «santa» en EDGAR     │
└──────────────────────────────────────────────────────────────────────┘
```

Las dos acciones del pie son **permanentes**, no del estado vacío. Es un fallo
que la revisión adversarial cazó: con `ITX` salen dos filas basura, así que el
estado vacío nunca se pinta y el camino honesto para Europa sería inalcanzable
justo cuando se necesita.

Badges: sólo los que se pueden **calcular**. `Analizable` / `Sólo cartera` /
`Comprobar al añadir` / `IFRS` / `Falta configuración`. **No** se promete un
badge ETF para las filas del índice SEC (su fichero no trae el tipo); las filas
externas sí lo traen del proveedor.

### 6.2. Comportamiento

- Debounce **250 ms**, `minLength` 2 (3 para la capa externa), `placeholderData`
  para que la lista no parpadee.
- Key de búsqueda **fuera** de `queryKeys.investment.all`, o adoptar el valor
  elegido refetchea la propia búsqueda.
- Teclado completo: ↑↓ Enter Esc, `role="combobox"` con nombre accesible,
  `aria-activedescendant`, y las filas no seleccionables con `aria-disabled` y el
  motivo **visible** (no sólo en un `title`).
- Plantilla a reutilizar: `apps/web/components/transactions/category-combobox.tsx`
  y su test — ya resuelve navegación por teclado y accesibilidad en este repo.

### 6.3. Diferencia Cartera vs Análisis (prop `intent`)

| | `intent='analysis'` | `intent='portfolio'` |
|---|---|---|
| Capa externa | **Nunca** | Sí, si el provider está activo |
| `no_annual` (SPY) | `aria-disabled` + motivo | Seleccionable |
| `not_supported` | No aparece | Seleccionable, badge «Sólo cartera» |
| Al elegir | `POST /adopt` → ingesta → run | `POST /adopt` → alta de lote |

### 6.4. Ficheros

Nuevos: `apps/web/components/investment/security-combobox.tsx` + su test.
Editados: `add-lot-form.tsx` (chip del valor elegido),
`app/(app)/investments/analysis/page.tsx` (`intent`),
`analysis/[securityId]/page.tsx`. Se borra `security-search.tsx` — si se deja,
`knip` lo marca en `make verify` (así se detectó el código muerto de PHASE-43).

---

## 7. Móvil

Mínimo imprescindible: quitar el `'US'` de la pantalla de análisis y pasar el
alta por `/search` + `/adopt`, para que analizar `MCD` desde el móvil cree **la
misma** fila que la web. El combobox rico con grupos y badges queda como
follow-up declarado, no como deuda silenciosa.

---

## 8. Entregas

### E1 — Higiene y verdad *(puede entrar en el commit de 44.7)*

No toca el componente, no añade columnas, no cambia el contrato de `onSelect` —
la prueba manual pendiente de 44.7 debe poder ejecutarse sobre el código que hay.

- `capabilities.py` en su forma mínima (`cik`), consumido por los tres sitios que
  hoy duplican la regla.
- `CompanyNotFoundError` → 404, con test que lanza la excepción **real** de la
  librería.
- Guarda de análisis sin CIK → 422 con motivo.
- Hook: debounce 250 ms + `minLength 2` + `placeholderData`; key fuera de
  `investment.all`.
- `resolveTyped` deja de mandar `'US'`; el servidor ignora el `exchange` del
  cliente.
- Borrar `PriceAdapter.symbol_search`.
- Ejecutar `normalize_security_exchanges.py` (son 2 filas reales: MCD y JNJ,
  ambas NYSE).
- **ADR-0008** + corregir `ARCHITECTURE-investment-module.md` §5 y
  `DESIGN-v2-investment-module.md`, que describen un buscador externo de tres
  pasos que este plan sustituye. Sin esto queda documentación describiendo algo
  que no existe — la lección de PHASE-43 sobre premisas que caducan en silencio.

**Aceptación**: teclear `MCDONALDS` produce **1** petición (hoy 9) y la lista no
parpadea · `resolve` con ticker inexistente devuelve **404** (hoy 500) ·
`Security` sin CIK → **422** con motivo · `grep -rn "exchange: 'US'" apps/web` → 0
· `grep -rn "cik is not None" backend/app` → **una** implementación ·
`SELECT DISTINCT exchange FROM securities` → sólo vocabulario válido · elegir un
valor no refetchea la búsqueda.

### E2 — Índice en memoria + capacidades por evidencia

`symbol_index.py`, `venues.py`, `ranking.py`, `capabilities.py` completos; la
migración de `analysis_status`; `POST /adopt`.

**Aceptación**: `q=coca` → `KO/NYSE` primero · `q=santander` → `SAN · Banco
Santander, S.A. · NYSE` en el **top 3** (hoy el ranking ingenuo lo manda al 6.º
de 8, detrás de dos pares duplicados de sus propias filiales OTC) · `q=itx` →
**sin** `ADTX` (predicado de nombre acotado por longitud de query), con el aviso
de alias de Inditex en el pie · `q=MC` → Moelis primero por ticker exacto ·
`q=spy` → badge «Comprobar al añadir», nunca «Analizable» · adoptar `SPY` deja
`analysis_status='no_annual'`; `SAN` → `'non_gaap'`; `MCD` → `'ok'` · adoptar la
línea OTC de un CIK ya adoptado **no** crea un segundo `Security` (assert de
`count(*)`) · buscar con **DNS bloqueado** devuelve resultados · `alembic
upgrade`/`downgrade` reversibles, `alembic check` sin drift, `alembic heads` una
sola línea.

### E3 — El combobox

`security-combobox.tsx` + test, prop `intent`, grupos, badges, estados, escapes
permanentes en el pie. Se borra `security-search.tsx`.

**Aceptación**: navegación completa por teclado sin ratón ·
`getByRole('combobox')` con nombre accesible · ninguna petición antes de 250 ms ·
en `intent='analysis'` la fila de SPY sale `aria-disabled` con motivo visible y
en `'portfolio'` es seleccionable · elegir un hit no refetchea la búsqueda.

### E4 — Paridad móvil mínima

**Aceptación**: analizar `MCD` desde el móvil crea la misma fila que la web
(`SELECT count(*) FROM securities WHERE ticker='MCD'` = 1).

### E5 — Capa externa multi-mercado *(la que responde a la petición original)*

`SymbolSearchAdapter` + `twelvedata.py` + factory apagada por defecto + caché en
memoria + `probe_twelvedata.py` ejecutado **antes** de escribir el mapeo.

**Aceptación**: con `investment_symbol_provider="none"` (default) el
comportamiento es idéntico a E3 y `external.enabled=false` · activado,
`intent=portfolio` + `q=santander` devuelve el grupo «Otros mercados» con Madrid
(XMAD/EUR) y LSE (XLON/GBp) · `intent=analysis` **nunca** llama al proveedor
(assert sobre el mock) · adoptar `SAN/XMAD` crea un `Security` con `currency='EUR'`,
`exchange='XMAD'`, `cik=NULL`, `analysis_status='not_supported'`, y **no**
colisiona con `SAN/NYSE` · el proveedor caído devuelve resultados locales y
`status='unavailable'`, no un 500 · `grep -rn "twelvedata" backend/app | grep -v
adapters/symbol_search` → 0 (el proveedor sólo se conoce en su adapter) · ninguna
tabla nueva y ningún `INSERT` derivado de una búsqueda externa.

---

## 9. Riesgos y decisiones abiertas

1. **La licencia de Twelve Data.** Su ToS prohíbe el uso comercial del free tier;
   para uso personal es defendible y la caché en memoria respeta el resto. Si
   Crisol llegara a comercializarse, el canje verificado es EODHD: €399/mes uso
   interno, €2.499/mes con display externo a clientes. El adapter aislado hace
   que ese cambio sean ~100 líneas.
2. **El keyless es indocumentado.** Funciona hoy y su propia documentación dice
   que la key es obligatoria. Puede cerrarse sin aviso: de ahí que E5 sea
   opt-in y que las capas 1-2 sean autosuficientes.
3. **Egreso de datos.** Con la capa externa activa, lo que teclees en Cartera
   sale hacia un tercero. Análisis nunca la llama. Decisión tuya, y es la razón
   de que el default sea `none`.
4. **`analysis_status` caduca.** Es una foto: quien hoy no publica 10-K puede
   publicarlo mañana. Mitigación obligatoria: recalcularlo en **cada ingesta**,
   no sólo al adoptar.
5. **El parquet se congela con la versión de la librería.** Un bump de
   `edgartools` que renombre la función o la columna deja el índice **vacío sin
   lanzar nada** (devuelve `None` y sólo hace `log.warning`). Por eso el test
   llama a la función real y falla ruidosamente con `None` o 0 filas, y por eso
   existe `index_ready`.
6. **Deriva del índice empaquetado.** Verificado contra el fichero vivo: 388
   tickers que el parquet no tiene y 341 que ya están deslistados (~7% de
   diferencia simétrica). El delta neto de 47 filas es la métrica equivocada
   porque las dos derivas se cancelan. Los ausentes los cubre la escotilla
   `typed:`; los deslistados fallan en `adopt` y deben salir con el 404 explicado.
7. **`pandas` no está declarada** en `backend/pyproject.toml`: entra como
   dependencia transitiva de `edgartools`. Documentarlo en el ADR y no importarla
   a nivel de módulo (~1 s en cada arranque).
8. **Los ADR extranjeros con CIK son el caso más traicionero.** SAN, ASML y SAP
   presentan 20-F con taxonomía `ifrs-full` contra un `concept_map` us-gaap: la
   ingesta podría terminar «bien» con casi todas las partidas vacías, y eso se
   lee como «esta empresa no publica datos», no como «el mapa no aplica». Probar
   en vivo con SAN o ASML antes de dar E2 por buena.
9. **Alias a mano.** Empezar con ~10 entradas (`ITX`→Inditex, `IBE`→Iberdrola…)
   y documentar el motivo de cada una **en el fichero**, no en el commit.

---

## 10. Trampas conocidas que aplican (de `lessons.md`)

- **«La forma de salida de una librería se PRUEBA, no se deduce»** (PHASE-44.6):
  de ahí `probe_twelvedata.py` antes de mapear un solo campo. Aplica igual al
  parquet de `edgartools`.
- **`getattr(obj, "metodo")` sin llamarlo es siempre truthy** (PHASE-44.6): el
  `is_financial_institution` de la librería es un método. Guarda `callable` al
  leer `venues` y cualquier flag nuevo.
- **Un hallazgo de código muerto es una hipótesis** (PHASE-43): antes de borrar
  `security-search.tsx` o `symbol_search`, grep de consumidores en web, móvil y
  tests.
- **Una premisa escrita en un comentario caduca en silencio** (PHASE-43): por eso
  E1 incluye editar ARCHITECTURE y DESIGN-v2, no sólo escribir el ADR.
- **Verificar con el intérprete equivocado da un verde que no vale**
  (PHASE-44.6): todo con `backend/.venv/Scripts/python.exe`, nunca el `python`
  del PATH. Y jamás dos `pytest` a la vez: `crisol_test` es compartida.
- **El padre de una migración se elige con `alembic heads`** (PHASE-44.1), no
  con `ls | tail`.

---

## 11. Definition of Done

- [ ] `make verify` verde (lint + typecheck + tests + knip + ruff + black + mypy)
- [ ] `alembic upgrade`/`downgrade` reversibles y `alembic check` sin drift
- [ ] Prueba manual: buscar `santander`, `MCD`, `spy`, `itx` y `MC` en las dos
      pestañas, con y sin la capa externa activa
- [ ] Prueba con DNS bloqueado (el índice local debe responder)
- [ ] ADR-0008 + ARCHITECTURE §5 y DESIGN-v2 corregidos
- [ ] `internal_docs/README.md` con la fase marcada y
      `internal_docs/api/endpoints.md` con `/adopt`
- [ ] Lección nueva en `lessons.md` si aparece un error evitable
