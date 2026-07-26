# Módulo de Inversión — Guía completa (lógica, decisiones, scripts, pruebas)

> Documento de referencia del módulo `investment` tras PHASE-44.7. Cubre la
> arquitectura y la lógica de cada capa, las decisiones tomadas (y por qué), qué
> hace cada script, el catálogo de endpoints y un **playbook de pruebas manuales**
> para validar el flujo completo antes de darlo por cerrado.
>
> Documentos relacionados: diseño lógico en
> [`improvements/DESIGN-v2-investment-module.md`](improvements/DESIGN-v2-investment-module.md),
> spec de implementación en
> [`improvements/ARCHITECTURE-investment-module.md`](improvements/ARCHITECTURE-investment-module.md),
> cierre en [`phases/phase-44.7-investment-module-fullstack.md`](phases/phase-44.7-investment-module-fullstack.md).

---

## 1. Qué es y estado

Módulo green-field de **inversión** con dos caras que comparten sólo el catálogo
de valores:

- **Análisis fundamental forense**: descarga los 10-K de la SEC de una empresa,
  los normaliza a un modelo canónico de 49 partidas y corre un **engine puro de 6
  capas** que produce un veredicto ("¿la contabilidad es de fiar? ¿genera caja?
  ¿el dividendo cabe? ¿aguanta un golpe?") con scores forenses (Beneish, Altman,
  Piotroski, Zmijewski, Montier), calidad de caja y seguridad del dividendo.
- **Cartera**: lotes, ventas casadas por **FIFO** (pool global por valor),
  dividendos, acciones corporativas (split/stock_dividend) y un resumen con valor
  de mercado (cuando hay cotizaciones).

**Estado**: construido de punta a punta (backend + web + móvil), verde en tests
automáticos (BE 1042 · FE lint/typecheck/tests/knip). **Sin prueba manual en vivo
todavía** — ese es el objetivo de este documento.

**Privacidad**: sólo sale de la máquina la petición a `data.sec.gov` (10-K
públicos) y, si se activa, a Finnhub (cotizaciones). Ningún dato del usuario.

---

## 2. Arquitectura en capas

```
                    ┌──────────────────────────────────────────────┐
   FRONTEND         │  web: Tab Análisis + Tab Cartera              │
   (web + móvil)    │  móvil: (modules)/investments (mismos hooks)  │
                    └───────────────────────┬──────────────────────┘
                                            │  @crisol/services (hooks TanStack)
                                            │  @crisol/types (modelos + DTOs)
                    ┌───────────────────────▼──────────────────────┐
   API              │  /investment/{securities,fundamentals,        │
   (FastAPI)        │   analysis,portfolio,pricing}                 │
                    │  router → service → repository                │
                    └───────────────────────┬──────────────────────┘
             ┌──────────────┬───────────────┼───────────────┬───────────────┐
             ▼              ▼               ▼               ▼               ▼
       ┌──────────┐  ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌──────────┐
       │ catálogo │  │ingesta    │   │ ENGINE     │   │ cartera    │   │ precios  │
       │(Security)│  │(EDGAR →    │   │ PURO       │   │(FIFO,      │   │(Finnhub, │
       │          │  │ canonical) │   │ 6 capas    │   │ corp.act.) │   │ TTL)     │
       └────┬─────┘  └─────┬─────┘   └─────┬─────┘   └─────┬─────┘   └────┬─────┘
            └──────────────┴───────────────┴───────────────┴──────────────┘
                                    PostgreSQL (13 tablas de 44.1)
```

**Regla de oro**: el `engine/` es **PURO** — sin BD, sin red, sin reloj (lo
verifica un test por AST). Toda la impureza (I/O, `datetime.now`) vive en los
`service.py`. Por eso el engine se testea con estados sintéticos y con fixtures
reales sin levantar Postgres.

### 2.1. Tablas (globales vs scoped)

| Tabla | Ámbito | Qué guarda |
|-------|--------|-----------|
| `securities` | GLOBAL | Identidad del valor (ticker, CIK, sector, is_reit/is_financial) |
| `financial_statements` | GLOBAL | 49 partidas por ejercicio y filing (`is_latest_view`) |
| `restatement_flags` | GLOBAL | Divergencias >1% entre filings del mismo año |
| `scoring_thresholds` | GLOBAL | Bandas por sector × norma × métrica |
| `price_quotes` | GLOBAL | Una cotización viva por valor (TTL) |
| `ingestion_jobs` | scoped (auditoría) | Estado de una descarga EDGAR |
| `analysis_runs` | scoped | Un run del engine (scores + JSONB) |
| `inv_lots`/`inv_sales`/`inv_sale_allocations` | scoped | Cartera + FIFO |
| `inv_dividends_received` | scoped | Dividendos cobrados |
| `inv_corporate_actions`/`inv_lot_adjustments` | scoped | Acciones corporativas + auditoría |

Lo global es objetivo (el 10-K de MCD es igual para todos → ADR-0007); lo scoped
es del usuario. La **posición NO es tabla**: se deriva de `lotes − allocations`.

---

## 3. Flujo end-to-end — Análisis (ticker → veredicto)

```
1. RESOLVE   POST /investment/securities/resolve {ticker, exchange}
             → EdgarAdapter.resolve(ticker): edgartools da CIK, SIC, is_reit,
               is_financial → sic_to_sector → crea el Security (GAAP, USD)

2. INGEST    POST /investment/fundamentals/{id}/ingest {filings_back:5}
             → crea IngestionJob(RUNNING); SÍNCRONO en la misma request:
               adapter.fetch_facts (descarga companyfacts, cachea el crudo)
               → build_raw_filings (ancla los hechos al ejercicio por fecha de
                 cierre; 10-K/FY; 350-380 días para años de 52/53 semanas)
               → normalize (mapea a 49 partidas canónicas, imputa ceros de la
                 lista blanca, deriva EBIT y total_liabilities, cuadra)
               → persiste FinancialStatement (upsert, flip is_latest_view)
               → detect_restatements → RestatementFlag
               → job DONE (o FAILED con error legible)

3. RUN       POST /investment/analysis/{id}/run {stress_params?}
             → build_series: FinancialStatement(BD) → CanonicalStatement
               (reconstruye item_provenance desde raw_source_ref['mapping'])
             → load_thresholds(sector, norma) + hash SHA-256
             → base_ratios → evolution → forensic → dividend → stress → synthesis
             → serializa las dataclasses a JSONB + mapea scores a columnas
             → persiste AnalysisRun (inmutable, versionado por engine+thresholds)

4. INFORME   El frontend pinta el AnalysisRun: veredicto de 4 preguntas + matriz
             de seguridad (Conservador/Vigilar/Evitar) + confianza + paneles.
```

**Por qué la ingesta es síncrona (no BackgroundTask)**: la descarga real es de
segundos y se cachea; el proxy de Next ya está a 5 min (lección PHASE-5.2); es
determinista de testear; y el contrato API (POST→job, GET job) es idéntico al de
un job en background, así que el polling del frontend no cambia. Mismo patrón que
`personal_finance.imports`.

**Por qué se reconstruye `item_provenance` en el builder**: el ORM
`FinancialStatement` no tiene columna de procedencia, pero el mapeo de la ingesta
la guardó en `raw_source_ref['mapping'][item]['provenance']`. Sin reconstruirla,
un `imputed_zero` contaría como `sourced` e **inflaría la confianza** del run
(§4.5 del DESIGN).

---

## 4. Flujo end-to-end — Cartera (compra → summary)

```
1. COMPRA    POST /investment/portfolio/lots {security_id, trade_date, qty, price}
             → Lot (pool global por valor)

2. VENTA     POST /investment/portfolio/sales {security_id, qty, price}
             → match_fifo(open_lots, qty): consume los lotes más antiguos primero;
               409 si vendes más de lo que tienes (nunca casa parcial en silencio)
             → SaleAllocation por cada trozo (guarda coste base + FX del lote)

3. SPLIT     POST /portfolio/corporate-actions {type:split, ratio:2}
             POST /portfolio/corporate-actions/{id}/apply
             → a los lotes anteriores a la fecha: qty×ratio, price÷ratio
               (coste base invariante) + LotAdjustment por auditoría (reversible)
             → spinoff/return_of_capital: aplicar devuelve 400 (no soportado aún)

4. SUMMARY   GET /investment/portfolio/summary
             → compute_position_cores: posición = Σ lotes − Σ allocations;
               coste base, P&L realizado, dividendos
             → refresh de cotizaciones caducadas (on-access TTL) vía PriceAdapter
             → valor de mercado, P&L latente (descompuesto precio/divisa), peso
             → posición sin cotización: market_value=null, fuera de los totales
```

**P&L precio vs divisa (opción A del usuario)**:
`price_effect = qty·(precio_actual − coste_medio)·fx_actual`,
`fx_effect = qty·coste_medio·(fx_actual − fx_compra)`. Sin feed de FX vivo
integrado, `fx_actual = fx_compra` → `fx_effect = 0` y `price_effect` recoge todo
el P&L latente. La fórmula reparte cuando el feed exista (sin tocar el código).

---

## 5. Sub-módulos backend (responsabilidad + ficheros)

Todos siguen `router → service → repository` (+ `models`/`schemas`). Ruta base
`backend/app/modules/investment/`.

| Sub-módulo | Responsabilidad | Ficheros clave |
|-----------|-----------------|----------------|
| `catalog/` | Buscar y resolver valores | `service.py`, `sic_mapping.py` (SIC→sector) |
| `fundamentals/` | Ingesta + persistencia | `service.py` (job), `restatements.py`, `normalization.py`, `canonical.py`, `validation.py`, `adapters/{edgar,annual,concept_map,factory}.py`, `cache.py` |
| `thresholds/` | Umbrales de scoring | `seed.py` (1440 filas), `service.py` (load + hash SHA-256 + seed_if_empty) |
| `analysis/` | Cablear engine ↔ BD | `service.py` (builder + orquestación), `serialization.py` (dataclass→JSONB), `engine/` (PURO, 6 capas) |
| `portfolio/` | Cartera | `fifo.py`, `corporate_actions.py`, `service.py` (posiciones derivadas) |
| `pricing/` | Cotizaciones + summary | `adapters/{base,finnhub,factory}.py`, `refresh.py` (TTL), `service.py` (summary §5.1) |

El engine (6 capas, `analysis/engine/`) es de fases anteriores (44.2-44.5) y no se
tocó en 44.7: `base_ratios` (27 métricas), `evolution` (horizontal/vertical/
coherencia), `forensic` (8 scores), `dividend` (D/Q/B/T), `stress` (ST1-ST3),
`synthesis` (4 preguntas + veredicto). `catalog.py` agrega las métricas — fuente
única de las `metric_key` del seed.

---

## 6. Decisiones tomadas (y por qué)

### 6.1. Decisiones del usuario (2026-07-23)

| # | Decisión | Razón |
|---|----------|-------|
| 1 | **Finnhub sin API key** → adapter completo pero cotizaciones/búsqueda DESACTIVADAS | No había key; la cartera funciona con datos manuales, valor "sin cotización" |
| 2 | **P&L opción A** (cruzado al efecto precio) | Convenio de broker habitual; sin residuo; efecto divisa sobre el coste original |
| 3 | **Split + stock_dividend** completos; spinoff/RoC registrar-sí-aplicar-no | El modelo `ratio` escalar no expresa security destino / fracción de base |
| 4 | **Inversión separada del patrimonio** + `AccountsGuard` eximido | Evita la exclusión de brokerage de PHASE-31.4; reconciliación diferida (40.9) |

### 6.2. Decisiones de diseño (heredadas o tomadas en 44.7)

- **Ingesta síncrona por job** (no BackgroundTask): testeable + proxy Next a 5 min
  + contrato API idéntico. (Ajuste consciente sobre el "async" inicial.)
- **`is_latest_view`**: cada año se colapsa a la vista vigente (el filing más
  reciente que lo reporta); el flip degrada otras versiones del mismo año.
- **Hash de umbrales** = SHA-256 del set resuelto en orden canónico → reproducibilidad
  del run (`AnalysisRun.thresholds_version`).
- **Seed de umbrales al arranque** (`seed_if_empty`, defensivo): si la BD está
  vacía siembra 1440 filas; si falla, el análisis cae a los defaults del engine
  (y en financieras el engine ya apaga los forenses por `is_financial`).
- **`total_liabilities` y `EBIT` derivados** (44.6): activo−patrimonio y
  pretax+intereses cuando faltan; se marcan `derived` y desactivan su comprobación
  testigo (el cuadre de balance se informa "no verificable", nunca "superado").
- **`pretax_income` como partida 49** (44.6): el EBIT se deriva de un dato
  reportado, no de `net_income + taxes` (que ignora minoritarios/discontinuadas).

### 6.3. Bug cazado en esta sesión

`is_financial_institution` de edgartools es un **método**, no un atributo; leerlo
con `getattr` sin llamarlo devolvía un bound method (siempre truthy) → **toda**
empresa salía financiera → forenses apagados. Cazado por el smoke en vivo;
arreglado con guarda `callable` + regresión. (Lección en `lessons.md`.)

---

## 7. Los scripts (`backend/scripts/`)

Todos con el intérprete del venv: `backend/.venv/Scripts/python.exe` (Python 3.12,
el de CI — **no** el global; ver lección PHASE-44.6).

| Script | Qué hace | Cómo correrlo |
|--------|----------|---------------|
| `edgar_smoke.py` | **Verificación en vivo** del pipeline de ingesta contra empresas reales: descarga → anclaje → normalización → cuadres, e imprime el resultado por ejercicio. NO es engine ni CI. | `EDGAR_IDENTITY="Nombre email" .venv/Scripts/python.exe scripts/edgar_smoke.py MCD O JNJ` (la 1ª vez descarga y cachea; luego offline) |
| `prune_edgar_fixtures.py` | Poda los `companyfacts` cacheados (3-4 MB) a los conceptos mapeados + datapoints 10-K → fixtures pequeñas (~100-350 KB) para el golden test | `.venv/Scripts/python.exe scripts/prune_edgar_fixtures.py` (lee de `EDGAR_CACHE_DIR`, escribe en `tests/fixtures/edgar/`) |
| `seed_investment_thresholds.py` | Siembra/refuerza `scoring_thresholds` a mano (el arranque ya lo hace vía `seed_if_empty`) | `.venv/Scripts/python.exe scripts/seed_investment_thresholds.py` |
| `validate_edgar.py` | (De 44.6, previo) el "cruzado": valida el mapeo concepto→partida contra empresas reales | `validate_edgar.py MCD:63908 O:726728 JNJ:200406` (offline con cache) |

### Lógica del smoke (`edgar_smoke.py`), en detalle

Es el mejor mapa de la ingesta pura. Para cada ticker:
1. `EdgarAdapter.resolve(ticker)` (o `TICKER:CIK` para evitar la red) → identidad.
2. `adapter.fetch_facts(identity)` → descarga `companyfacts` (o cache) y parsea a
   `XbrlFact` con el parser real de edgartools. Guarda el crudo (auditoría).
3. `filing_refs(facts)` → los 10-K disponibles.
4. `build_raw_filings(facts, limit=5)` → un `RawFiling` por ejercicio, **anclado
   por fecha de cierre** (no por la etiqueta `fy` del informe, que en un 10-K es
   la misma para las 3 columnas comparativas).
5. `normalize(raw)` por ejercicio → `CanonicalStatement` (49 partidas + procedencia
   + `quality_flags` de los cuadres).
6. Imprime las partidas vertebrales con su procedencia (`sourced`/`derived`/
   `imputed_zero`), el margen neto, los huecos y los avisos de cuadre.

Qué mirar en la salida (validado en el cruzado): EBIT `sourced` en MCD y `derived`
en O y JNJ; `total_liabilities` `derived` en MCD (no publica `Liabilities`) → cuadre
de balance NO VERIFICABLE; márgenes ~31,9% (MCD) / 18,4% (O) / 28,5% (JNJ); huecos
= ausencias reales (sin COGS en servicios, balance no clasificado del REIT).

---

## 8. Catálogo de endpoints

Prefijo `/investment`. Todos exigen usuario autenticado (Bearer). Importes/ratios
como string decimal.

```
# Catálogo
GET  /securities/search?q=&limit=          buscador (catálogo local)
POST /securities/resolve {ticker,exchange} crea/reutiliza el Security vía EDGAR
GET  /securities/{id}

# Fundamentales
POST /fundamentals/{id}/ingest {filings_back}   → 202, IngestionJob (done/failed)
GET  /fundamentals/jobs/{jobId}                 estado del job (scoped)
GET  /fundamentals/{id}/statements?view=latest|all
GET  /fundamentals/{id}/restatements

# Análisis
POST /analysis/{id}/run {stress_params?}   → 200 AnalysisRun (409 si sin datos)
GET  /analysis/{id}/runs                   histórico (scoped)
GET  /analysis/runs/{runId}

# Cartera
POST/GET/DELETE /portfolio/lots            (GET ?security_id=)
POST/GET/DELETE /portfolio/sales           (POST ejecuta FIFO; 409 si qty>held)
POST/GET/DELETE /portfolio/dividends
POST /portfolio/corporate-actions          registra
GET  /portfolio/corporate-actions
POST /portfolio/corporate-actions/{id}/apply   split/stock_dividend (400 el resto)
GET  /portfolio/positions                  posiciones derivadas (sin mercado)

# Precios
POST /pricing/refresh {security_ids?}      fuerza refresh (botón manual)
GET  /portfolio/summary                    posiciones + valor de mercado (§5.1)
```

---

## 9. Playbook de pruebas manuales

Objetivo: validar el flujo real que los tests automáticos no cubren (SEC en vivo +
UI). Marca cada paso conforme lo compruebes.

### 9.0. Requisitos previos

- [ ] Postgres arriba (`docker compose up -d postgres`).
- [ ] `backend/.env` con `EDGAR_IDENTITY="Nombre email"` (ya configurado).
      Opcional: `FINNHUB_API_KEY=...` para cotizaciones en vivo.
- [ ] Backend: `cd backend && .venv/Scripts/python.exe -m uvicorn app.main:app --reload`
- [ ] Frontend web: `pnpm dev:web` (o `pnpm dev`).
- [ ] Estar logueado (usa tu usuario; Inversión NO exige cuenta de finanzas
      personales — se puede probar con un usuario recién creado).

### 9.1. Análisis (web) — el flujo estrella

1. [ ] Sidebar → **Inversiones** aparece como módulo activo (no "Próximamente").
       Al pinchar, cae en **Cartera**; cambia a la pestaña **Análisis**.
2. [ ] En el buscador escribe `MCD`. Como no está en el catálogo local, sale el
       botón **"Analizar «MCD» en EDGAR"**. Púlsalo.
   - *Qué valida*: `resolve` contra la SEC. Debe navegar a la página del valor con
     la cabecera `MCD · McDonald's · consumer discretionary`. Si no es financiera,
     NO debe salir el badge "Financiera" (regresión del bug arreglado).
3. [ ] Sale la CTA **"Descargar 10-K (EDGAR)"**. Púlsala.
   - *Qué valida*: la ingesta síncrona en vivo. Tarda unos segundos (descarga
     ~3,5 MB). Al volver, la CTA desaparece y aparece **"Ejecutar análisis"** con
     "N ejercicios ingeridos (2021, 2022, …)".
   - *Si falla*: el job vuelve `failed` con un error legible (SEC caída, sin CIK).
4. [ ] Pulsa **"Ejecutar análisis"**.
   - *Qué valida*: el engine cableado. Aparece el **informe**: tarjeta de veredicto
     (4 preguntas con semáforo, perfil Conservador/Vigilar/Evitar, "dividendo…",
     confianza X%) + 3 paneles (Forense, Calidad y solvencia, Dividendo) con
     valores y bandas + pie "Motor v1.0.0 · ejercicios … · umbrales …".
   - *Contraste*: el margen neto y los scores deben ser coherentes; MCD debe salir
     con Z''/M-Score razonables (equity negativo por recompras es normal).
5. [ ] Prueba un **REIT** (`O`) y una **farma** (`JNJ`):
   - `O`: EBIT derivado, rama FFO del dividendo, forenses `not_computable` con
     razón (REIT/financiera), no huecos silenciosos.
   - `JNJ`: EBIT derivado (dejó de publicar resultado operativo en 2015), sin huecos.

### 9.2. Cartera (web)

6. [ ] Pestaña **Cartera**. Pulsa **"Añadir compra"**, elige un valor (búscalo o
       resuélvelo), pon cantidad y precio, **"Añadir compra"**.
   - *Qué valida*: `POST /lots`. La posición aparece en la tabla con cantidad y
     coste base.
7. [ ] Sin `FINNHUB_API_KEY`: el valor de mercado sale **"sin cotización"** y hay
       una nota de que las cotizaciones están desactivadas. Con key: **"Actualizar
       precios"** trae el precio y calcula valor de mercado + P&L latente + peso.
8. [ ] (API) Vende más de lo que tienes → debe dar **409** ("solo tienes N").
9. [ ] (API) Registra un `split` ratio 2 y aplícalo → cantidad ×2, precio ÷2,
       coste base intacto (`GET /portfolio/lots`). Un `spinoff` → aplicar da **400**.

### 9.3. Móvil (opcional)

10. [ ] `pnpm dev:mobile`. En el switcher de módulos aparece **Inversiones** con
        sus tabs Cartera/Análisis. En Análisis: teclea `MCD` → Buscar → Descargar
        10-K → Ejecutar análisis → veredicto de 4 preguntas.

### 9.4. Validación por API (sin UI, con curl/httpie)

```bash
# token: regístrate o loguéate y copia el access_token
TOKEN=...
BASE=http://localhost:8000/investment   # ajusta el puerto de uvicorn
AUTH="Authorization: Bearer $TOKEN"

# resolver + ingerir + analizar MCD
SID=$(curl -s -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"ticker":"MCD","exchange":"NYSE"}' $BASE/securities/resolve | jq -r .id)
curl -s -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"filings_back":5}' $BASE/fundamentals/$SID/ingest | jq '.status,.progress'
curl -s -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{}' $BASE/analysis/$SID/run | jq '.dividend_verdict,.confidence,.verdict.questions[].verdict'
```

---

## 10. Limitaciones conocidas y follow-ups

- **Sin API key de Finnhub**: precios y búsqueda externa desactivados.
- **Summary en divisa nativa** de cada posición (sin conversión a base con FX
  vivo); los totales mezclan divisas si la cartera es multi-moneda.
- **Spinoff / return_of_capital**: registrar sí, aplicar no (falta modelo con
  security destino + fracción de base).
- **Charts del informe** (evolución common-size, stress, heatmap de Δ%) y
  **statement viewer**: diferidos; el informe MVP muestra veredicto + métricas.
- **Paridad móvil completa del informe**: sólo el veredicto (los paneles de
  métricas y charts son follow-up — es ~3 entregas como marcó el análisis).
- **Sin tests de componente FE** específicos del módulo (la lógica está cubierta
  en backend + services); follow-up.
- **`10-K/A` (enmiendas)** y ejercicios sin 10-K propio: fuera a propósito (ver
  cabos sueltos en el doc de 44.6).
- **Prueba manual en vivo**: pendiente (este documento). Hasta hacerla, el pipeline
  está validado con hechos sintéticos y fixtures reales, pero el flujo UI + SEC en
  vivo no se ha ejecutado end-to-end.
```
