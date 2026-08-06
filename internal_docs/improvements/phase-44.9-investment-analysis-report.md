# PHASE-44.9 — Informe de análisis fundamental con pestañas (plan de fase)

> **Estado**: ⏳ pendiente (plan). Siguiente a PHASE-44.8 E1.
> **Alcance**: backend (`backend/app/modules/investment/`) + web
> (`apps/web/app/(app)/investments/analysis/`, `apps/web/components/investment/`).
> **Fuera de alcance**: paridad móvil (ver §6).
> **Origen**: el motor calcula 51 métricas, 18 banderas, 6 escenarios de stress y
> un dictamen con su porqué; la pantalla pinta 22 filas de un solo ejercicio y
> desaparece al recargar.
> **Metodología del usuario**: `internal_docs/ai-context/excel-analisis-empresas.md`
> (10 hojas, leído entero).
>
> **Convención de esta ficha**: toda afirmación sobre el código lleva
> `fichero:línea` verificada leyendo el fichero en esta sesión. Lo que no he
> leído va marcado explícitamente como **no verificado**.

---

## 1. La idea en una frase

Convertir la pantalla de análisis en un **dossier navegable**: un *hero*
persistente con el titular, **seis pestañas en la URL** —Estados · Ratios ·
Evolución · Forense · Dividendo · **Veredicto y porqué** (la última, la que se
abre por defecto)—, cada celda con su banda, su procedencia y el corte contra el
que se juzga, leyendo el **run persistido** en vez del resultado volátil de una
mutación.

---

## 2. Diagnóstico — qué se pinta hoy vs qué se calcula y se guarda

### 2.1. El informe vive en una mutación y muere al recargar

`apps/web/app/(app)/investments/analysis/[securityId]/page.tsx:122`:

```tsx
{run.data ? <AnalysisReport run={run.data} /> : null}
```

`run` es `useRunAnalysis()` (`page.tsx:39`), una **mutación**. Al refrescar la
página el informe desaparece y hay que volver a ejecutar el análisis. Los dos
hooks que leen el histórico existen y **no los llama nadie**:
`useAnalysisRuns` (`packages/services/src/query/hooks/useInvestment.ts:118`) y
`useAnalysisRun` (`:126`).

### 2.2. Se pintan 22 de 51 métricas, y todas del mismo año

`ALL_METRIC_DEFINITIONS` agrega los cuatro catálogos de capa
(`backend/app/modules/investment/analysis/engine/catalog.py:19-24`). Recuento
verificado leyendo cada catálogo:

| Capa | Fichero | Métricas | Con banda |
|---|---|---|---|
| Capa 1 — base | `engine/base_ratios.py:59-185` | 27 | 17 |
| Capa 1.5 — evolución | `engine/evolution.py:72-96` | 2 | 1 (E3) |
| Capa 2 — forense | `engine/forensic.py:60-161` | 8 | 8 |
| Capa 3 — dividendo | `engine/dividend.py:86-201` | 14 | 14 |
| **Total** | `engine/catalog.py:19-24` | **51** | **40** |

Las **11 sin banda** salen siempre con `band=null`, que **no significa "sana"**:
A1-A5 (`base_ratios.py:78-87`), R1-R4 (`:131-134`), R8 (`:146-154`) y E4
(`evolution.py:86-95`) se declaran sin `direction`, y `ThresholdSpec.band_for`
documenta que `None` «NO es lo mismo que 'sano'»
(`engine/types.py:185-190`).

La web declara 8 + 7 + 7 = **22 filas** (`apps/web/components/investment/analysis-report.tsx:10-39`).
**Faltan 29**: `L2 L3 L4 A1 A2 A3 A4 A5 S1 S3 S4b S5 S6 R1 R2 R3 R5 R6 R8 R9b`
(20 de capa 1), `E3 E4` (2), `D1 D6 Q3 Q5 B3 T2 T3` (7 de dividendo).

Y todo el informe se congela en el último ejercicio:
`latestYear()` (`metric-row.tsx:39-41`) usado en `analysis-report.tsx:43`,
mientras el JSONB trae **todos** los años (la banda se calcula por año en
`engine/metrics.py:88-96`, sin filtro de ejercicio).

### 2.3. Tres etiquetas de la web contradicen al motor

| Web | Motor | Fórmula real |
|---|---|---|
| `'F5 — deuda emergente'` (`analysis-report.tsx:15`) | «Riesgo de fondo de comercio» (`forensic.py:112`) | goodwill / activo total (`forensic.py:569-576`) |
| `'F6 — dilución'` (`analysis-report.tsx:16`) | «Anomalía del circulante» (`forensic.py:124`) | \|Δcirculante operativo\| − Δventas (`forensic.py:579-599`) |
| `'Rentabilidad por dividendo'` (`analysis-report.tsx:36`) | «Margen de seguridad» (`dividend.py:142`) | (caja repartible − dividendos) / ventas (`dividend.py:497`) |

Es consecuencia directa de que el catálogo no viaje por API (§5). La tercera es
la peor: la rentabilidad por dividendo exige **precio**, que el run no tiene.

### 2.4. Lo que se calcula, se persiste y nadie mira

`analysis/service.py:179-192` compone seis columnas JSONB
(`analysis/models.py:58-63`, todas `NOT NULL`) pasando las dataclasses por
`to_json_safe` (`analysis/serialization.py:20-39`, que vuelca **todos** los
campos de cada dataclass sin lista blanca).

| Estructura persistida | Dónde se genera | ¿La pinta la web? |
|---|---|---|
| `scores_detail.forensic.breakdowns[]` (M-Score 8 vars, Z'' X1-X4, F-Score 9 tests, C-Score 6 checks) | `forensic.py:177-189`, emisión `:676-722` | **No** |
| `scores_detail.base_ratios.dupont[]` (3 factores, cada uno un `MetricResult`) | `base_ratios.py:201-212`, `:262-280` | **No** |
| `evolution.horizontal[]` (7 series con YoY, base 100, CAGR y `cagr_reason`) | `evolution.py:118-126`, `:131-151` | **No** |
| `evolution.vertical[]` (common-size, 23 balance + 12 P&L por año) | `evolution.py:194-242` | **No** |
| `dividend_analysis.dps_series[]` y `.trajectory` (racha T1, T4) | `dividend.py:227-231`, `:244-254` | **No** |
| `flags[]` (18 claves posibles) | `synthesis.py:167` | **No** |
| `verdict.stress` (6 escenarios con frase redactada + ST3) | `stress.py:37-77`, `service.py:190` | **No** |

Los tipos TS lo tratan como un saco: `MetricCollection` es
`{ metrics; flags?; [key: string]: unknown }`
(`packages/types/src/models/investment.ts:232-236`) y `VerdictBlock.stress` es
`Record<string, unknown>` (`:228`). Pesa en cada respuesta, no está tipado y no
se pinta.

El propio motor lo pide por escrito: *«el agregado es la parte MENOS informativa
… La UI enseña el desglose, no solo el número»* (`forensic.py:181-183`).

### 2.5. El «por qué» está a medias — y las 3 cadenas buenas no se usan

Lo que **sí** llega redactado en español hoy:

- `Flag.message` + `Flag.evidence` (`engine/types.py:242-249`) — 18 claves.
- `SafetyProfile.blocking_reasons` (`synthesis.py:79-85`), p. ej. *«M-Score y
  accruals ambos en rojo (manipulación probable)»* (`:339`).
- `StressScenario.sentence` (`stress.py:169-172`, `:190-194`).
- `MetricResult.reason`, obligatoria en `not_computable` (`types.py:238-239`).
- `HorizontalSeries.label` y `.cagr_reason` (`evolution.py:143-150`).

Lo que **no** llega:

- **`label`, `family` y `note` de las 51 métricas**: viven sólo en
  `MetricDefinition` (`engine/metrics.py:33-42`) y ningún endpoint las sirve.
- **Los cortes del umbral**: `to_metric_result` usa el `spec` y lo **tira**
  (`engine/metrics.py:88-96`); `MetricResult` no lo lleva (`types.py:224-230`).
- **Las señales de cada pregunta**: `QuestionVerdict.red_signals/amber_signals`
  son `tuple[str]` sin valor ni corte (`synthesis.py:70-76`), y **8 de ellas son
  la clave cruda**: `_flag_signal(name, flags)` devuelve el `name` que recibe
  (`synthesis.py:125-133`) y las llamadas le pasan `"Q4_tax_anomaly"`,
  `"C1_receivables_vs_revenue"`, `"C2_income_without_cash"`,
  `"C3_inventory_vs_cogs"`, `"Q4_tax_persistently_low"` (`:218-222`),
  `"B1_debt_competes_with_dividend"`, `"B2_interest_priority"`,
  `"B4_dividend_funded_externally"` (`:259-261`). La web las funde y las imprime
  tal cual: `[...q.red_signals, ...q.amber_signals]` (`verdict-card.tsx:53`) →
  `signals.join(' · ')` (`:74`). Hoy el usuario lee literalmente
  `M-Score · B4_dividend_funded_externally`.

### 2.6. Contabilidad de endpoints y de deuda documental

- **25 endpoints** en el módulo (`grep -c "@router\.(get|post|put|patch|delete)"`
  sobre `backend/app/modules/investment` → 25). Ninguno de catálogo de métricas.
- `backend/app/modules/investment/thresholds/` contiene `__init__.py`,
  `models.py`, `repository.py`, `seed.py`, `service.py` — **sin `router.py`**
  (listado del directorio).
- `internal_docs/api/endpoints.md`: **0 coincidencias** de «investment».
- `ENGINE_VERSION = "1.0.0"` (`engine/version.py:17`) y su historial sólo
  documenta «PHASE-44.2: Capa 1» (`:12`), pese a haber entrado después las capas
  1.5, 2, 3, 3.5 y 4. Su docstring afirma que *«el golden test … es el gate que
  impide tocar una fórmula en silencio»* (`:8-9`); ese gate **no existe**: `grep
  ENGINE_VERSION backend/` sólo lo encuentra en `version.py`,
  `engine/__init__.py:19-21`, `analysis/service.py:33,167` y
  `tests/test_investment_engine.py:35,191`, donde lo único que se comprueba es
  el **formato semver** (`:191` hace `ENGINE_VERSION.split(".")`).

### 2.7. Estados degradados que la pantalla actual no contempla

| Situación | Qué pasa en el motor | Cita |
|---|---|---|
| Financiera | los 8 forenses salen `not_computable` con la razón EXACTA `"modelo no aplicable a financieras"` | `forensic.py:50-52`, `:649-655` |
| Financiera (efecto colateral) | el perfil **jamás** puede ser Conservador: exige los 5 checks forenses en verde | `synthesis.py:350-356` |
| Financiera (efecto colateral 2) | las 5 señales de banda de «contabilidad» desaparecen; si ninguna bandera se enciende, `_aggregate` cae al `else: verdict = "healthy"` — **verde por ausencia de prueba** | `synthesis.py:139-147` |
| Sin dividendo o financiera | `dividend_verdict = "not_applicable"` **cortocircuitando antes** de mirar las preguntas, mientras `_question_dividend` sí se ejecuta y puede salir rojo | `synthesis.py:178` vs `:375-380` |
| Primer ejercicio de la serie | `m_score`, `f_score`, `F6`, `F7` → `not_computable` («sin ejercicio N−1 no hay variación interanual que comparar») | `forensic.py:689-695` |
| < 3 ejercicios | E3 no calculable (`MIN_YEARS_FOR_SIGMA = 3`) y T3 tampoco (`MIN_YEARS_FOR_PAYOUT_STABILITY = 3`) | `evolution.py:65-67`, `dividend.py:61-63` |
| Balance no clasificado (REIT, financieras) | `current_assets`/`current_liabilities` quedan FUERA de la lista de imputables a cero a propósito → L1/L2/L3 no calculables | `adapters/concept_map.py:414-418` |
| Servicios sin COGS | `cogs` fuera de la misma lista → A2, A3, A5, R1, R10 no calculables | ídem |
| REIT | Z'' se calcula pero se etiqueta con bandera ámbar `z_score_uncalibrated_for_reit` | `forensic.py:657-669` |

> Los recuentos empíricos por empresa (MCD: 1 desglose forense de 8; Realty
> Income: 0 de 8 y `compl=0.700` por los dos huecos de balance) proceden de la
> **verificación adversarial ejecutada sobre las fixtures del repo**; yo no he
> re-ejecutado el engine en esta sesión. Marcados como *no re-verificados por mí*
> allí donde se usan.

---

## 3. Arquitectura de la pantalla

### 3.0. Decisiones transversales

**D1 — El veredicto va dos veces.** El usuario pidió «una parte final con el
veredicto y su porqué»; el motor se autodescribe como *«Lo que la UI muestra
PRIMERO»* (`synthesis.py:3`). Se cumplen ambos: **hero persistente** encima de la
barra + **pestaña 6, la última**, con el dictamen completo. Al entrar sin `?tab=`
se aterriza en la 6.

**D2 — La pestaña viaja en la URL** (`?tab=estados&sub=balance`), siguiendo la
convención de filtros en URL de PHASE-27, como **query param y no como segmento
de ruta**: una sola página conserva la caché del run al cambiar de pestaña.

**D3 — Multi-año por defecto.** La unidad de presentación es la **matriz: una
fila por concepto, una columna por ejercicio** — la forma del cuaderno («una
columna por año, 2016–2020», `excel:279`). **Todas** las celdas se colorean con
su banda, porque la banda se calcula para todos los años
(`engine/metrics.py:88-96`); lo que se marca aparte es **cuál es el ejercicio que
alimenta el dictamen**: `year = series.years[-1]` (`synthesis.py:165`) y los
escalares del run son de `last_year` (`service.py:152`, `:170-176`).

**D4 — Seis reglas de honestidad, idénticas en las seis pestañas.**

| # | Regla | Fundamento |
|---|---|---|
| a | `null` en una partida es **HUECO**, nunca 0 | las 49 columnas son nullable a propósito (`canonical.py:5`, `fundamentals/schemas.py:59-111`) |
| b | `status === 'not_computable'` muestra su `reason` **visible**, no en `title=` | hoy se esconde en `title=` (`metric-row.tsx:86`); el motor garantiza razón (`types.py:238-239`) |
| c | `band === null` es **gris «sin banda»**, nunca verde | `types.py:185-190` |
| d | `provenance !== 'sourced'` se marca con punto + leyenda | `canonical.py:29-53`; se lee de `raw_source_ref.mapping[<item>].provenance` (§3.1) |
| e | lo que el motor no calcula se lista en gris **con motivo**, nunca se omite | `types.py:6-10` |
| f | **`status === 'approximation'` se marca** (input degradado, típicamente sin t−1) | `types.py:27-29`; hoy la web lo pinta como número normal (`metric-row.tsx:69` sólo distingue `not_computable`) |

**D5 — Estados degradados de primera clase.** Los nueve casos de la tabla §2.7,
cada uno con su `degraded-panel` y su copy. Se añaden dos que la propuesta
original no contemplaba: **balance no clasificado** y **serie corta** (tabla de
«qué muere con 1 / 2 / 3 ejercicios»).

**D6 — Sistema de diseño existente.** `Card` / `CardTitle`
(`apps/web/components/ui/card.tsx:25`, `:51`) — **`CardHeader` NO existe**
(verificado: `card.tsx` sólo exporta esos dos; la fila de PHASE-38.3 del README
está caducada). `BandChip` / `bandColors` como semáforo único
(`metric-row.tsx:6-37`). Tokens de `@crisol/ui` con estilos inline (ADR-0001).
Grids con `repeat(auto-fit, minmax(min(100%, Npx), 1fr))` —el idiom del repo,
`apps/web/app/(app)/dashboard/page.tsx:214`— y **no** el
`minmax(300px, 480px)` que usa hoy el informe (`analysis-report.tsx:51`) y que
desborda por debajo de 300 px. Tablas anchas: `overflowX: 'auto'` **dentro** de
su Card, como `apps/web/components/ui/data-table.tsx:81`.

**D7 — Bajo ~640 px la matriz colapsa** a «un ejercicio a la vez»: selector de
año + lista concepto ↔ valor. La página nunca hace scroll horizontal.

### 3.0.1. Estructura de navegación

```
┌───────────────────────────────────────────────────────────────────────┐
│ MCD  McDonald's Corp   [consumer discretionary]                       │
│                                                                       │
│  ┌──────────────┐   ● ¿Contabilidad?  ● ¿Genera caja?                 │
│  │ CONSERVADOR  │   ● ¿Dividendo?     ● ¿Aguanta golpe?               │
│  └──────────────┘                                                     │
│  Dividendo sano · Confianza 92% · ejercicio 2025 ▾ · run 26-jul 18:04 │
│                                                        [Re-ejecutar]  │
├───────────────────────────────────────────────────────────────────────┤
│ Estados │ Ratios │ Evolución │ Forense │ Dividendo ┊ VEREDICTO        │
└───────────────────────────────────────────────────────────────────────┘
```

Hero (fuente por elemento):

| Elemento | Campo exacto |
|---|---|
| identidad, badges | `GET /investment/securities/{id}` → `ticker`, `name`, `sector`, `is_reit`, `is_financial` (ya en `page.tsx:55-64`) |
| chip de perfil | `run.verdict.safety_profile.label` (`synthesis.py:79-85` → `service.py:188`) |
| 4 puntos | `run.verdict.questions[].verdict`, en el orden fijo accounting/cash/dividend/resilience (`synthesis.py:175-180`) |
| estado del dividendo | `run.dividend_verdict` (columna, `models.py:53`) |
| confianza | `run.data_completeness.value` (`synthesis.py:87-95`) |
| fecha y cobertura | `run.run_date`, `run.years_covered` |

**Dos reglas nuevas del hero, ambas derivadas de defectos verificados:**

1. **Punto gris «sin evidencia»** cuando una pregunta no evaluó **ninguna**
   señal. Sin esto, un banco pinta **verde** en «¿La contabilidad es de fiar?»
   permanentemente, por el `else: verdict = "healthy"` de `_aggregate`
   (`synthesis.py:139-147`) con los 8 forenses apagados (`forensic.py:649-655`).
   El cliente **no puede** saberlo hoy: `QuestionVerdict` no lleva cuántas
   señales se evaluaron (`synthesis.py:70-76`) → **BLOQUEANTE 3** (§5).
2. **Punto neutro en «¿El dividendo cabe en la caja?»** cuando
   `run.dividend_verdict === 'not_applicable'`. Si no, el hero se autocontradice:
   «Sin dividendo relevante» junto a un punto rojo, porque el cortocircuito de
   `_dividend_verdict` (`synthesis.py:375-380`) es anterior a la pregunta, que sí
   se ejecuta (`:178`).

---

### 3.1. Pestaña 1 · ESTADOS — hojas 2, 3 y 4 del cuaderno

Nivel 2 (`?sub=`): **Balance · Resultados · Flujo de caja · Series**.

**Fuente**: `GET /investment/fundamentals/{security_id}/statements?view=latest`
(`fundamentals/router.py:75-86`), que devuelve las 49 partidas como columnas
(`fundamentals/schemas.py:41-114`) en **orden ascendente por ejercicio**
(`fundamentals/repository.py:33-42`, `order_by(fiscal_year)`).

**Cotejo obligatorio**: los `fiscal_year` de los statements contra
`run.years_covered`. Si el usuario reingirió después del run, el balance en
pantalla puede tener años que el dictamen no juzgó.

**Agrupación**: los sub-bloques del balance (activo corriente / no corriente /
pasivo corriente / no corriente / patrimonio) son **comentarios de Python**
(`canonical.py:82-111`), no datos; lo que viaja son 49 claves planas snake_case
(`fundamentals/schemas.py:58-111`). El agrupamiento y las etiquetas ES hay que
servirlos desde el backend (**BLOQUEANTE 1b**, §5) o duplicar 49 literales en TS
— exactamente el mecanismo que produjo los rótulos F5/F6/D8.

- **Balance (23)**: `canonical.py:82-111`, orden y bloques ya coinciden con
  `excel:93-125`.
- **Resultados (16)**: `canonical.py:113-130`, reordenadas en los 5 bloques del
  cuaderno (`excel:140-146`). `shares_basic` y `shares_diluted` juntas porque el
  usuario pide vigilar la brecha (`excel:146,151`) — y se dice que **el motor no
  la calcula** (ninguna métrica del catálogo consume `shares_diluted`).
- **Flujo (10)**: `canonical.py:132-143`, en las 3 actividades (`excel:160-164`),
  con aviso de convención de signos (todas positivas con semántica fija:
  `canonical.py:11-13`).
- **Series (E1)**: las **7 magnitudes exactas** con su etiqueta ya en español —
  Ventas, EBIT limpio, Resultado neto, Flujo de explotación, Caja libre,
  Dividendos pagados, Acciones en circulación (`HORIZONTAL_ITEMS`,
  `evolution.py:118-126`) — desde `run.evolution.horizontal[]`, con YoY,
  base 100 y CAGR; si no hay CAGR se pinta `cagr_reason` (`evolution.py:147-150`).

**Conmutador € / % / Δ** sobre la tabla:
`%` = `run.evolution.vertical[]` (`VerticalPoint{fiscal_year, item, base, weight}`,
`evolution.py:212-219`).

> **Aviso obligatorio, corregido**: el common-size **no cubre el flujo de caja
> NI 4 partidas del P&L**. `VERTICAL_INCOME_ITEMS` son 12
> (`evolution.py:194-207`) y dejan fuera `pretax_income`, `shares_basic`,
> `shares_diluted`, `shares_outstanding_eop`; el docstring (`:208-209`) sólo
> justifica los recuentos de acciones — `pretax_income` no está justificado. El
> balance sí va completo (`:226`, sobre `CANONICAL_BALANCE_ITEMS`).

**Trazabilidad del dato (bloque nuevo, injerto de la verificación).** Los cuadres
de ingesta **no son** `Flag` del engine y por tanto **no están en `run.flags`**:
`validation.py:8-12` lo dice literalmente («la `Flag` del engine habla del
NEGOCIO … esta habla del DATO y vive en `raw_source_ref`»). Se persisten en
`raw_source_ref['quality_flags']` (`normalization.py:358-365`) y se sirven en
`StatementResponse.raw_source_ref` (`fundamentals/schemas.py:113`). Las cuatro
claves: `balance_identity_unverifiable` (`validation.py:90-100`),
`balance_identity_broken` (`:105-120`), `net_margin_out_of_range` (`:135-149`),
`components_exceed_total` (`:171-187`). Se pintan **por ejercicio, junto a la
fila `total_liabilities`** — es la única pestaña donde tienen sentido.

La procedencia por partida se lee de
`items[].raw_source_ref.mapping[<partida>].provenance`
(`normalization.py:95`; así lo reconstruye el propio backend en
`analysis/service.py:56-66`). **No existe un campo `provenance` plano**: quien
implemente debe buscarlo ahí o acabará pintando todo como `sourced`.

```
┌ ESTADOS ─────────────────────────────────────────────────────────────┐
│ [Balance] Resultados  Flujo de caja  Series      € │ % común │ Δ     │
│                                                                      │
│ ⚠ 2018–2025 · El cuadre del balance no es verificable: el pasivo     │
│   total no venía en el filing y se dedujo restando el patrimonio.    │
│                                                                      │
│ ACTIVO CORRIENTE            2021    2022    2023    2024    2025•    │
│  Efectivo                  4.709   2.584   4.579   1.087   1.284     │
│  Activos financieros ct.       —·      —·      —·      —·      —·    │
│  Deudores                  2.224   2.115   2.379   2.428   2.510     │
│  Existencias                  —       —       —       —       —      │
│  Total activo corriente    7.148   4.923   7.161   4.243   4.575     │
│ ACTIVO NO CORRIENTE                                                  │
│  Inmovilizado material    24.721  24.397  24.813  25.161  25.400     │
│  Fondo de comercio         2.776   2.718   2.361   2.353   2.360     │
│  …                                                                   │
│ ──────────────────────────────────────────────────────────────────── │
│ Total activo              53.854  50.435  56.147  53.802  55.180  ⚠  │
│                                                                      │
│ · = cero imputado (el filing no publica el concepto)                 │
│ — = hueco (el filing no lo da; no es cero)                           │
│ • = ejercicio que alimenta el dictamen                               │
└──────────────────────────────────────────────────────────────────────┘
```

---

### 3.2. Pestaña 2 · RATIOS — hojas 5 a 9 del cuaderno

Nivel 2: **Liquidez · Actividad · Solvencia y deuda · Rentabilidad · DuPont**.
Matriz métrica × ejercicio, agrupada por la `family` que ya declara el catálogo.

**Fuente**: `run.scores_detail.base_ratios.metrics[]` y `.dupont[]`
(`service.py:181`; estructura `base_ratios.py:215-219`, `:201-212`) +
`run.thresholds_used[key]` (nuevo, **BLOQUEANTE 2**) + catálogo
(**BLOQUEANTE 1**).

- **Liquidez** — L1, L2, L3 + **L4 Muro de vencimientos**, marcado como añadido
  del motor con su `note`: *«el mecanismo por el que las empresas quiebran de
  verdad (no poder refinanciar), y que L1-L3 no miran»* (`base_ratios.py:71-75`).
- **Actividad** — A1-A5 con cabecera que avisa de que **ninguna tiene banda** y
  del motivo que da el motor: *«un DSO de 45 días es excelente en retail y pésimo
  en software»* (`metrics.py:28-31`). El foco es la deriva: gráfico de líneas +
  banderas C1 y C3.
- **Solvencia y deuda** — S1-S6 con las dos lecturas enfrentadas que el motor ya
  escribe: S2 vs S6 (*«Si S2 sale verde y S6 rojo, el devengo está mintiendo»*,
  `base_ratios.py:125-128`) y S4 vs S4b (*«en negocios con amortización alta, el
  EBITDA infla la capacidad de repago aparente»*, `:104-107`). Calendario de
  vencimientos apilado desde `short_term_debt` / `ltd_current_portion` /
  `long_term_debt`.
- **Rentabilidad** — R1-R10 + R9b, con **los márgenes formateados como %**
  (hoy `formatMetricValue` imprime `0,42` para un margen del 42 %,
  `metric-row.tsx:51-56`, y ninguna fila pasa `suffix`).
- **DuPont** — ROE · margen neto · rotación · apalancamiento, una columna por
  año, igual que `excel:279-282`. Cada factor es un `MetricResult` completo
  (`base_ratios.py:201-212`). **Se declara** que el extendido de 5 factores y la
  fila «Check» no existen (§6). Aviso: `DUPONT_EM` se emite con una key que **no
  está en el catálogo** (`base_ratios.py:262`), así que `definition_for` devuelve
  `None` → es uno de los cuatro rótulos que la UI asume (§5).

**Filas en gris con motivo** (el cuaderno las pide, el motor no las tiene):
ratio de endeudamiento (pasivo/patrimonio, `excel:235`) y calidad de la deuda
(corto/total, `excel:236`).

**Casos degradados reales que esta pestaña debe soportar** *(recuentos de la
verificación adversarial, no re-verificados por mí; el mecanismo sí está
verificado en `concept_map.py:414-418`)*: en MCD, `A2 A3 A5 R1 R10` salen
`not_computable` por falta de `cogs` y `R5`/`DUPONT_EM` por patrimonio medio
negativo (guarda `require_positive_denominator=True`, `base_ratios.py:265-270`);
en Realty Income, `L1 L2 L3` caen por falta de `current_assets`. La sub-pestaña
«Liquidez» de un REIT queda con **una** fila. La barra de nivel 2 debe marcar las
sub-pestañas sin ninguna métrica calculable **antes** de que el usuario las abra.

```
┌ RATIOS ──────────────────────────────────────────────────────────────┐
│  Liquidez │ Actividad │ [Solvencia y deuda] │ Rentabilidad │ DuPont   │
│                                                                      │
│                        2021   2022   2023   2024   2025•   límite    │
│ S1 Apalancamiento      1,03   1,08   1,02   1,04   1,03    >0,75 ✕   │
│ S2 Cobertura int.       8,1    7,4    7,9    7,2    6,8    <3 / <6   │
│ S4 Deuda neta/EBITDA    3,4    3,6    3,3    3,4    3,3    <2 / <3,5 │
│ S4b Deuda neta/EBIT     4,1    4,4    4,0    4,1    4,0    <3 / <5   │
│ S5 Años de repago       3,9    4,3    3,8    4,0    3,9    <4 / <8   │
│ S6 Cobertura por caja  10,2    9,5   10,1    9,3    8,9    <4 / <8   │
│                                                                      │
│ ℹ S2 usa EBIT (devengo, maquillable); S6 usa caja generada. Si S2    │
│   sale verde y S6 rojo, el devengo está mintiendo.                   │
│                                                                      │
│ El cuaderno pide, y el motor no calcula:                             │
│   Ratio de endeudamiento (pasivo/patrimonio, óptimo 1–2)   — no hay  │
│   Calidad de la deuda (corto/total, óptimo 20–40 %)        — no hay  │
└──────────────────────────────────────────────────────────────────────┘
```

---

### 3.3. Pestaña 3 · EVOLUCIÓN — los «Vigilar» del cuaderno, hechos computables

**Fuente**: `run.evolution` (`service.py:184`).

- **E2 en el tiempo**: mapa de pesos por partida y año (mismos `vertical[]`).
- **E3** estabilidad del margen EBIT (banda `high_ok=2`, `high_alarm=5` pp,
  `evolution.py:76-79`) y **E4** crecimiento sostenible, **sin banda por diseño**
  (`evolution.py:90-94`).
- **Banderas C1-C8 + `growth_externally_funded`** desde
  `run.evolution.flags[]`, cada una con su `message` y su `evidence` desplegable
  (`types.py:242-249`). Aquí se resuelven los «Vigilar» del cuaderno:
  inventarios vs ventas (`excel:128`) → C3 (`evolution.py:409-423`); ventas
  planas (`excel:149`) → serie `revenue` con su CAGR; dilución (`excel:151`) →
  C6 (`evolution.py:488-509`).

**Agrupación obligatoria por `key`.** Las banderas se emiten **por ejercicio o
por racha** y se concatenan sin deduplicar (`synthesis.py:167`): un REIT puede
traer 7 tarjetas idénticas de dilución *(recuento de la verificación
adversarial, no re-verificado)*. `flag-list.tsx` agrupa por clave y presenta los
años como rango.

---

### 3.4. Pestaña 4 · FORENSE — lo que el cuaderno no tiene

**Fuente**: `run.scores_detail.forensic` → `.metrics[]`, `.breakdowns[]`,
`.flags[]` (`forensic.py:192-208`) + `run.z_variant`.

Ocho tarjetas con su **etiqueta REAL** del catálogo (`forensic.py:60-161`):
M-Score de Beneish · Z''-Score de Altman (`model_variant="Z''(1995)"`) ·
F-Score de Piotroski · Accruals de Sloan · **Riesgo de fondo de comercio (F5)** ·
**Anomalía del circulante (F6)** · X-Score de Zmijewski · C-Score de Montier.

> **Corrección respecto al diseño ganador**: el cuerpo normal de una tarjeta es
> **valor + banda + razón**; el desglose es un **bloque opcional**, no la
> estructura. Sólo 4 de las 8 claves pueden emitir `ScoreBreakdown` y además de
> forma condicional (`if z_variables:` `:678`, `if m_variables:` `:699`,
> `if f_tests:` `:706`, `if c_checks:` `:719`); `accruals`, `F5`, `F6` y `FZ`
> **nunca** lo emiten (`forensic.py:177-189`). En financieras no hay ninguno
> (`:649-655` devuelve `ForensicResult(metrics=...)` con `breakdowns=()`).
> *Empíricamente, MCD trajo 1 desglose de 8 y Realty Income 0 (verificación
> adversarial, no re-verificado por mí).*

La tarjeta distingue **tres** estados, no dos:
1. «este score no tiene desglose por diseño» (accruals, F5, F6, FZ);
2. «este año no hay desglose porque el score no se pudo calcular» (con la razón:
   p. ej. «no se pueden calcular las variables GMI del M-Score»,
   `forensic.py:328-332`);
3. desglose presente → componentes (M-Score 8 vars, Z'' X1-X4) o checks binarios
   (F-Score 9, C-Score 6).

**Financiera**: la pestaña se sustituye por un `degraded-panel` con la razón
literal `NOT_APPLICABLE_TO_FINANCIALS` (`forensic.py:50-52`) y su consecuencia
sobre el perfil (`synthesis.py:350-356`).

---

### 3.5. Pestaña 5 · DIVIDENDO

**Fuente**: `run.dividend_analysis` (`service.py:183`) + escalares
`run.fcf_payout` (D2) y `run.fcf_coverage` (D3) (`service.py:175-176`).

Cuatro bloques con las 14 métricas del catálogo (`dividend.py:86-201`):

- **Cobertura**: D1, D2, D3, D4, D5, D6, D8.
- **Calidad de caja**: Q1, Q2, Q3, Q5.
- **Soporte de balance**: B3 + banderas B1, B2 y **B4**.
- **Trayectoria**: `dps_series[]` (`DpsPoint{fiscal_year, dps}`,
  `dividend.py:227-231`), `trajectory{streak_no_cut, momentum_slowdown}`
  (`:244-254`) y **T2/T3 aquí, no en la matriz**.

> **Corrección**: `_year_metrics` emite **12** métricas por ejercicio
> (`dividend.py:464-515`); **T2 y T3 se añaden una sola vez con `last_year`**
> (`:626-630`). Ponerlas en la matriz produciría una fila con una celda poblada
> y N−1 huecos indistinguibles de un `not_computable`.

Copy que ya escribe el motor y hay que usar tal cual: D2 es la primaria (*«la
caja, no el beneficio, es lo que paga el dividendo»*, `dividend.py:103`); D4
(*«si D4 ≫ D2 el dividendo se paga diluyendo»*, `:120`). **D8 = «Margen de
seguridad»**, no rentabilidad por dividendo (`:142`, cálculo `:497`).

**D6 en no-REIT**: la razón que **viaja** es
`"solo aplica a socimis (is_reit=false)"` (`dividend.py:489-493`) — **no** el
texto de la `note` (`:138`), que hoy no sirve ningún endpoint. En REIT las bases
cambian a FFO (`profit_base`/`cash_base`, `dividend.py:210-221`).

La racha se rotula con la advertencia del propio motor: *«es una COTA INFERIOR:
la serie es la ingerida, no la histórica completa»* (`dividend.py:249-250`). Ni
T1 ni T4 tienen banda ni entran en ningún semáforo.

---

### 3.6. Pestaña 6 · VEREDICTO Y PORQUÉ — la «parte final»

Nivel 2: **Dictamen** · **Confianza y datos**.

#### Dictamen — seis bloques

**1. Perfil como checklist auditable, no como sello.** Se imprimen las reglas
literales de `_safety_profile` (`synthesis.py:325-360`) con su ✔/✘ y el valor de
cada métrica: *Evitar* si (m_score rojo **Y** accruals rojo) o z_score rojo o FZ
rojo o B4 rojo; *Conservador* sólo si se cumplen las 5 (m_score, z_score, FZ,
accruals en verde + `f_score >= 7`); en el resto, *Vigilar* con las condiciones
incumplidas. Debajo, `blocking_reasons` tal cual — hoy el único sitio donde el
motor redacta el porqué completo.

**2. Las cuatro preguntas, desplegables.** Texto en español ya redactado por el
motor (`:224`, `:245`, `:263`, `:280`) y **la regla del semáforo impresa**:
«rojo si ≥1 señal roja; ámbar si ≥2 ámbar; verde en el resto»
(`_aggregate`, `synthesis.py:136-147`), más el aviso de que una métrica sin banda
o no calculable **no cuenta ni a favor ni en contra** (`_band_signal`, `:119-122`).

Al desplegar, la tabla de señales candidatas con su valor y su banda. **Requiere
BLOQUEANTE 3**: hoy las señales son cadenas y **no se pueden cruzar con las
métricas**, ni por clave (no viaja) ni por etiqueta (ya divergen). Divergencias
verificadas etiqueta-señal vs etiqueta-catálogo:

| Señal (`synthesis.py`) | Catálogo |
|---|---|
| `"M-Score"` (`:213`) | «M-Score de Beneish» (`forensic.py:63`) |
| `"C-Score (Montier)"` (`:214`) | «C-Score de Montier» (`forensic.py:150`) |
| `"Accruals"` (`:215`) | «Accruals de Sloan» (`forensic.py:99`) |
| `"Estabilidad de márgenes"` (`:242`) | «Estabilidad del margen EBIT» (`evolution.py:75`) |
| `"Z''-Score"` (`:271`) | «Z''-Score de Altman» (`forensic.py:76`) |
| `"X-Score (Zmijewski)"` (`:272`) | «X-Score de Zmijewski» (`forensic.py:136`) |

**Fallback si BLOQUEANTE 3 se aplaza**: para las 8 señales que son clave cruda
(§2.5), hacer JOIN contra `run.flags[]` por `key` para recuperar el `message`
redactado — que sí está persistido (`service.py:185`). Es un arreglo barato y de
alto valor. Para las 7 de banda no hay fallback honesto: se pintan sólo con su
nombre y se declara que no se puede enseñar el valor.

**Mapa pregunta → señales, verificado** (`synthesis.py:202-280`):

| Pregunta | Señales de banda | Señales de bandera | Total |
|---|---|---|---|
| accounting `:212-223` | m_score, F7, accruals, Q3, Q5 | Q4_tax_anomaly, Q4_tax_persistently_low, C1, C2, C3 | 10 |
| cash `:235-244` | Q1, Q2, f_score, R7, R9b, R10, E3 | (tendencia FCF, `_fcf_trend_signal` `:283-291`) | 8 |
| dividend `:252-262` | D2, D3, D4, D5, D6, B3 | B1, B2, B4 | 9 |
| resilience `:270-279` | z_score, FZ, L4, S2, S4, S5, S6 | (stress, `_stress_signal` `:294-319`) | 8 |

**3. Stress, plegado dentro de «¿Aguanta un golpe?»** (no merece pestaña propia:
son 6 escenarios con la frase ya redactada). Fuente `run.verdict.stress`
(`service.py:190`; estructura `stress.py:47-68`). Cada escenario con su
`sentence` y la etiqueta fija `"escenario hipotético"` (`HYPOTHETICAL_LABEL`,
`stress.py:32`, `:56`), más `breakeven_fcf_drop` (ST3) y `contribution_margin`.

> **Dos correcciones duras, ambas verificadas:**
>
> **(a)** `not_computable_reason` se rellena **exclusivamente** cuando la serie
> no tiene ejercicios (`stress.py:141-147`). Cuando `estimate_contribution_margin`
> devuelve `None`, el bucle ST1 no se ejecuta (`:158`) y el `return` final
> (`:201-205`) **no pasa ningún motivo**: llega `null` y desaparecen 3 de los 6
> escenarios sin explicación. **La UI redacta ella el motivo** cuando
> `contribution_margin === null` («no se pudo estimar el apalancamiento operativo
> con esta serie, así que el shock de ingresos no se calcula»), o se corrige en
> backend (§5, no bloqueante).
>
> **(b)** El stress usa **caja libre pura**: `fcf_base = dv.fcf_cfo(latest).value`
> (`stress.py:149`), **sin** el ajuste REIT que sí aplica la capa 3
> (`cash_base` = FFO si `is_reit`, `dividend.py:217-221`). En un REIT la
> pestaña 5 puede decir «cobertura 1,3× a vigilar» y la 6 «cobertura −0,22×». El
> bloque se rotula **«cobertura sobre caja libre (CFO − capex), no sobre FFO»** y
> **no** se presenta como recálculo de D3.

**4. Todas las banderas, en dos grupos honestos**: «mueven el veredicto» y «sólo
informan». Las `info` no puntúan por diseño (`_flag_signal`, `synthesis.py:125-133`),
y **10 de las 18 claves no están cableadas a ninguna pregunta**: sólo 8 aparecen
en `synthesis.py:202-280` (Q4×2, C1, C2, C3, B1, B2, B4). C5, C6, C7
—**incluso en rojo**, `evolution.py:524-533`— y `growth_externally_funded`
pueden encenderse sin mover nada, y hay que decirlo.

**5. Alcance — qué NO cubre este informe** (§6).

**6. Reproducibilidad**: `run_date`, `years_covered`, `thresholds_version`
**completo** (hoy truncado a 8 caracteres, `analysis-report.tsx:74-75`) y
`engine_version` **presentado como identificador informativo, no como garantía**
mientras siga congelado en `1.0.0` con seis capas dentro (§2.6).

#### Confianza y datos

La fórmula desmontada con los seis campos de `Confidence`
(`synthesis.py:87-95`): completitud sobre las **10 partidas núcleo** enumeradas
(`CORE_ITEMS`, `synthesis.py:46-57`) × años, `imputed_zero` contados aparte
porque no cuentan como sourced (`:410-413`), y frescura 1,0 / 0,7 / 0,4 en los
cortes de 274 y 548 días (`:60-61`, `:423-428`). Hoy la web ignora
`staleness_factor` y `latest_fiscal_year_end` (`verdict-card.tsx:99-105`).

**Matriz de cobertura** partida núcleo × ejercicio. Declaración obligatoria de
fuente y limitaciones:

- **No sale del run**: `Confidence` agrega y pierde el detalle
  (`synthesis.py:403-414`). Hay que ir a
  `GET /fundamentals/{id}/statements` → `raw_source_ref.mapping[<item>].provenance`
  (`normalization.py:95`), hoy tipado como `Record<string, unknown>`
  (`packages/types/src/models/investment.ts:161`).
- **Puede desmentir al run** si el usuario reingirió: mismo cotejo contra
  `years_covered` que en la pestaña 1.
- **Cuatro estados, no tres**: sourced · imputada · ausente · **«cero legítimo /
  no aplica a este tipo de balance»**. Sin el cuarto, el ejemplo se vuelve en
  contra: `dividends_paid` está a la vez en `CORE_ITEMS` (`synthesis.py:52`) y en
  `IMPUTABLE_ZERO_ITEMS` (`concept_map.py:401`) — en una empresa que no reparte
  no «falta», vale cero; y en un REIT la pérdida de 30 puntos de completitud es
  **estructural** (`current_assets`/`current_liabilities` fuera de la lista blanca
  a propósito, `concept_map.py:414-418`), no un hueco reparable. Sin esa nota, el
  usuario reingerirá una y otra vez buscando arreglar algo que no está roto.

Debajo: tabla de procedencia por métrica (`MetricResult.provenance`) e
**historial de runs** (`GET /investment/analysis/{id}/runs`).

```
┌ VEREDICTO Y PORQUÉ ──────────────────────────────────────────────────┐
│ [Dictamen] │ Confianza y datos                                       │
│                                                                      │
│ PERFIL: CONSERVADOR                                                  │
│  Evitar si…                                                          │
│   ✕ M-Score y accruals ambos en rojo   (−2,41 verde · 0,031 verde)   │
│   ✕ Z''-Score en rojo                  (3,82 verde)                  │
│   ✕ X-Score en rojo                    (−1,94 verde)                 │
│   ✕ Dividendo financiado con deuda      (bandera B4 no encendida)    │
│  Conservador exige las 5…                                            │
│   ✔ M-Score verde  ✔ Z'' verde  ✔ X-Score verde                     │
│   ✔ F-Score ≥ 7 (7)  ✔ Accruals verde                               │
│                                                                      │
│ ▸ ¿La contabilidad es de fiar?                          [Sano]       │
│ ▾ ¿Aguanta un golpe?                                    [Vigilar]    │
│    Regla: rojo si ≥1 roja · ámbar si ≥2 ámbar · verde el resto.      │
│    Señal                      valor    banda    ¿puntúa?             │
│    Z''-Score de Altman         3,82    verde     sí                  │
│    Deuda neta / EBITDA         3,30    ámbar     sí  (>2)            │
│    Años de repago              3,90    verde     sí                  │
│    Muro de vencimientos          —     —         no calculable       │
│    Escenario de stress        0,98×    rojo      sí                  │
│                                                                      │
│    ESCENARIOS · sobre caja libre (CFO − capex), no sobre FFO         │
│    [escenario hipotético] Con las ventas cayendo un 20 %, la         │
│    cobertura del dividendo por caja libre pasa de 1,42× a 0,98×.     │
│    Margen antes de dejar de cubrir (ST3): 29 %.                      │
│                                                                      │
│ BANDERAS QUE MUEVEN EL VEREDICTO (2) · SÓLO INFORMAN (4)             │
│ ALCANCE: lo que este informe NO cubre → valoración, sector, …        │
│ Motor 1.0.0 (identificador) · umbrales 9f3a…c17 · run 26-jul 18:04   │
└──────────────────────────────────────────────────────────────────────┘
```

---

### 3.7. Componentes nuevos (todos en `apps/web/`)

| Fichero | Qué es | Por qué no se reutiliza algo |
|---|---|---|
| `components/ui/tabs.tsx` | Nivel 1. `role="tablist"/"tab"/"tabpanel"`, sincronizado con `?tab=`, `overflow-x:auto`, colapso a `<select>` bajo ~480 px | **No existe**: `apps/web/components/ui/` no tiene `tabs.tsx` (listado del directorio). `ModuleSections` es navegación de **ruta** |
| `components/ui/segmented.tsx` | Nivel 2, genérico | Hay **4 tablist ad-hoc** (`grep role="tablist"`): `amortization/page.tsx:484`, `stitch-expense-breakdown.tsx:514`, `effort-ratio-section.tsx:155`, `convert-to-debt-dialog.tsx:241` |
| `components/investment/year-matrix.tsx` | Matriz concepto × ejercicio: 1ª columna fija, scroll interno, colapso a un-año | la usan las pestañas 1, 2, 3 y 5 |
| `components/investment/metric-line.tsx` | Evolución de `MetricRow`: valor **por unidad**, `BandChip`, `reason` visible, punto de procedencia, marca de `approximation`, popover con `note` y el corte | `metric-row.tsx:51-56` no tiene noción de unidad; `:69` no distingue `approximation`; `:86` esconde la razón |
| `components/investment/score-breakdown-card.tsx` | Bloque **opcional** con `components` / `checks` | — |
| `components/investment/flag-list.tsx` | `message` + `evidence` desplegable, **agrupado por `key`** con rango de años, etiquetas «no puntúa» / «informativa» | — |
| `components/investment/signal-table.tsx` | Señales de una pregunta con valor y banda | — |
| `components/investment/degraded-panel.tsx` | Financiera · sin dividendo · serie corta · balance no clasificado | — |
| `components/investment/metric-index.ts` | `Map<"key|year", MetricResult>` construido una vez | `findMetric` es lineal (`metric-row.tsx:43-49`): irrelevante con 22 filas, no con 51 × N años |

Y sustituir `<p>Cargando…</p>` (`page.tsx:66`) y los `<span>` rojos sueltos
(`page.tsx:89-95`, `:114-118`) por `Skeleton`/`SkeletonCardList`
(`apps/web/components/ui/skeleton.tsx`) y `ErrorState`
(`apps/web/components/ui/error-state.tsx`), que existen y el módulo no usa.

Se retiran: `analysis-report.tsx` y `metrics-card.tsx` (previo grep de
consumidores en `apps/web` **y** `apps/mobile`, ver §9).

---

## 4. El veredicto y su POR QUÉ

**Cómo se presenta**: hero (titular, siempre visible) + pestaña 6 (dictamen
completo). El perfil se pinta como **checklist auditable** con el valor de cada
métrica al lado, no como un sello. Cada pregunta se abre y enseña **la regla del
semáforo impresa** y **todas** sus señales candidatas, incluidas las que no
puntuaron por no tener banda o no ser calculables.

**Qué se puede construir HOY, sin tocar el backend** (corrección al diseño
ganador, que decía «las 6 pestañas completas salvo el umbral»):

- ✅ Perfil como checklist con `blocking_reasons` (`synthesis.py:79-85`).
- ✅ Las 4 preguntas con su texto y su banda.
- ✅ Los 6 escenarios de stress con su `sentence` (`stress.py:169-172`, `:190-194`).
- ✅ Las 18 banderas con `message` + `evidence` (`types.py:242-249`).
- ✅ Las razones de `not_computable` (`types.py:238-239`).
- ✅ Las 7 series E1 con su `label` ya en español (`evolution.py:118-126`).
- ✅ La matriz multi-año con bandas (se calculan todos los años,
  `metrics.py:88-96`).
- ❌ El **valor y el corte** de cada señal de una pregunta.
- ❌ El «frente a qué umbral» de cualquier métrica.
- ❌ El **nombre, la familia, la nota y la unidad** de las 51 métricas.
- ❌ El **nombre y el grupo en español** de las 49 partidas.
- ❌ El punto gris «sin evidencia» del hero.

Es decir: sin backend hay que **hardcodear 51 etiquetas + 49 nombres de
partida** — exactamente el mecanismo que produjo F5/F6/D8. Por eso los tres
bloqueantes de §5 son **pre-requisito de las pestañas 1, 2, 4, 5 y 6**, no
follow-ups.

---

## 5. Trabajo de backend vs trabajo de frontend

### 5.1. ¿Hay migraciones? **Sí, una.**

```
alembic revision -m "investment: persist effective thresholds in analysis_run"
→ ADD COLUMN analysis_runs.thresholds_used JSONB NOT NULL DEFAULT '{}'::jsonb
```

Aditiva y reversible. Los runs anteriores quedan con `{}` y **no podrán
explicarse retroactivamente** — se dice en pantalla, no se finge.

Ninguna otra entrega toca el esquema: los cambios de forma de
`QuestionVerdict` y del catálogo viajan dentro de JSONB ya existentes
(`analysis/models.py:58-63`) o son endpoints de sólo lectura.

> **Por qué columna propia y no una clave dentro de `verdict`**: `verdict` es el
> veredicto; meterle 40 especificaciones de umbral repite el error de mezclar dos
> responsabilidades en el mismo contenedor
> (`internal_docs/lessons.md`, [PHASE-23.1]).

### 5.2. BLOQUEANTE 1 — catálogo por API (sin migración)

**1a. Métricas.** `GET /investment/analysis/metrics` → las 51
`MetricDefinition` con `key`, `label`, `family`, `direction`, los 4 cortes por
defecto, `model_variant`, `note` y un campo **nuevo `unit`**
(`ratio | times | percent | days | pp | score | currency | count`), que
`MetricDefinition` **no tiene** hoy (`engine/metrics.py:33-42`) y sin el cual 51
métricas heterogéneas se leen como números sin escala.

**Cuatro claves que el catálogo NO cubre y hay que resolver**, o seguirán
hardcodeadas: `DUPONT_EM` (`base_ratios.py:262`, fuera de `METRIC_CATALOG`) y las
tres familias de stress `ST1_revenue_-NN` / `ST2_rates_+NNNbps` / ST3
(`stress.py:165`, `:186`). Recomendación: añadir `DUPONT_EM` al catálogo (sin
`direction`, así **no añade ninguna fila al seed** — `build_threshold_rows` itera
`ALL_DEFAULT_THRESHOLDS`, que sólo contiene las banded, `thresholds/seed.py:58`)
y declarar las tres de stress como rótulos de UI asumidos.

**1b. Partidas canónicas.** `GET /investment/fundamentals/items` → las 49 con
etiqueta ES y grupo (balance-corriente / balance-no-corriente / … / flujo-inversión).
Los grupos existen hoy **como comentarios** (`canonical.py:82-143`).

### 5.3. BLOQUEANTE 2 — los umbrales EFECTIVOS del run

No basta con exponer `scoring_thresholds`, porque **los cortes de un run pasado
son hoy irrecuperables**:

- `UniqueConstraint("sector","accounting_std","metric_key")`
  (`thresholds/models.py:57-61`) — sin versión ni vigencia.
- El seed **muta la fila existente in situ** (`thresholds/service.py:104-110`).
- `thresholds_version` es un SHA-256 irreversible (`thresholds/service.py:58-78`):
  sirve para **detectar** deriva, nunca para reconstruirla.
- `load_thresholds` fusiona BD **sobre** los defaults del engine
  (`thresholds/service.py:48-51`), así que ni leyendo la tabla se reproduce el
  juego usado.

→ **Persistir el juego efectivo dentro del run**: `thresholds_used` (la
migración de §5.1), rellenado en `analysis/service.py:145-146` con
`to_json_safe(thresholds)`, y expuesto en `AnalysisRunResponse`
(`analysis/schemas.py:26-53`).

### 5.4. BLOQUEANTE 3 — señales estructuradas

`QuestionVerdict` (`synthesis.py:70-76`) pasa a llevar, además de las dos tuplas
actuales (que se conservan por compatibilidad con runs viejos):

```
signals: tuple[QuestionSignal, ...]
  QuestionSignal = { key, label, kind: 'metric'|'flag', band: Band|None,
                     value: Decimal|None, status, counted: bool }
evaluated_count: int      # señales con banda conocida
unavailable_count: int    # las que no contaron
```

Resuelve tres cosas de golpe: el valor junto a la señal, el punto gris del hero
(§3.0.1) y las 8 claves snake_case (`synthesis.py:218-222`, `:259-261`). Cambia
la salida del engine → **`ENGINE_VERSION` a 1.1.0** con su entrada de historial.

### 5.5. No bloqueantes, por orden de valor

1. `GET /investment/analysis/{security_id}/runs/latest` → `AnalysisRunResponse`
   completa (404 si no hay). Sin él, aterrizar en la pestaña 6 exige **dos
   peticiones encadenadas**: `AnalysisRunSummary` no lleva **ningún** JSONB
   (`analysis/schemas.py:56-69`) y el único endpoint con desglose es
   `GET /analysis/runs/{run_id}` (`analysis/router.py:47-55`). *Recomendación:
   subirlo a E1: está en la ruta crítica del primer píxel.*
2. `stress.compute` rellena `not_computable_reason` también cuando
   `contribution_margin is None` (`stress.py:158`, `:201-205`).
3. `ENGINE_VERSION` al día + **golden test atado a la constante**, que hoy no
   existe pese a que su docstring lo afirma (`version.py:8-9`; el único test lo
   comprueba como semver, `tests/test_investment_engine.py:188-191`). O se ata, o
   se borra la afirmación del docstring.
4. Tipado real de los seis JSONB en Pydantic y TS (`MetricCollection` es un saco
   con index signature, `packages/types/src/models/investment.ts:232-236`).
5. `investmentApi.listRuns` devuelve el envoltorio `{items}`
   (`endpoints/investment.ts:93-98`) mientras el resto desenvuelve (`:66-75`,
   `:111-117`): corregir o documentar.
6. Common-size del flujo de caja y de las 4 partidas de P&L que faltan
   (`evolution.py:194-207`).
7. Restatements en la síntesis: hay endpoint (`fundamentals/router.py:89`) y el
   motor declara que aún no entran (`synthesis.py:210-211`).
8. Documentar los 25 endpoints en `internal_docs/api/endpoints.md` (**0
   coincidencias de «investment»** hoy).

### 5.6. Sólo frontend

Todo lo de §3.7 + la reescritura de
`apps/web/app/(app)/investments/analysis/[securityId]/page.tsx` (leer run
persistido, `?tab=&sub=`, estados de carga/error/«aún no hay análisis») + tipar
`AnalysisRun` de verdad en `packages/types/src/models/investment.ts` + cablear
`useAnalysisRuns` / `useAnalysisRun` (`useInvestment.ts:118`, `:126`).

---

## 6. Lo que NO entra, y por qué

### 6.1. Valoración por múltiplos (hoja 10 del cuaderno) — **no entra**

Tres hechos comprobables, no una preferencia:

1. **El engine no recibe precio.** `SecuritySnapshot` sólo tiene `ticker`,
   `sector`, `accounting_std`, `is_financial`, `is_reit`
   (`engine/types.py:38-52`). No hay por dónde entrar.
2. **Es una decisión de reproducibilidad, escrita**: *«Todos book-based y
   deterministas: ninguno depende del precio de mercado, porque un score que se
   mueve con la cotización no sería reproducible al reejecutar un run antiguo»*
   (`forensic.py:3-6`).
3. **El proveedor está apagado en esta instalación**: `finnhub_api_key: str = ""`
   (`backend/app/core/config.py:135`) y `backend/.env` no define `FINNHUB_API_KEY`
   (`grep -c FINNHUB backend/.env` → 0).

Y el propio cuaderno reconoce que la comparativa «vs sector» necesita una fuente
de múltiplos sectoriales que **no existe en el proyecto** (`excel:372-378`).

**Qué se pinta en su lugar**: el bloque **«Alcance — qué NO cubre este informe»**
en la pestaña 6, con las tres causas **separadas** y qué haría falta para cada
una. Es más honesto que una pestaña vacía y **caduca sola** cuando alguien ponga
la API key.

**Cómo debería entrar en el futuro** (propuesta, PHASE-44.x): una capa de
valoración **fuera del engine y fuera del `AnalysisRun`** —un endpoint que cruce
cotización viva × último statement— para que el run siga siendo reproducible. Se
aplaza hasta que exista API key.

### 6.2. Resto de lo que queda fuera

| Qué | Por qué | Qué se hace |
|---|---|---|
| DuPont extendido de 5 factores + fila «Check» (`excel:284-290`) | no existe en el motor: `DuPontDecomposition` sólo tiene 3 factores (`base_ratios.py:201-212`) | fila en gris con motivo. **Follow-up barato**: los 3 factores que faltan son derivables de partidas ya presentes y, **sin `direction`, no añaden filas al seed** (`thresholds/seed.py:58`) |
| Ratio de endeudamiento (`excel:235`) y calidad de la deuda (`excel:236`) | no están entre las 51 claves | filas en gris con motivo; follow-up S7/S8 |
| FCF de mantenimiento, «recomendado» por el cuaderno (`excel:184`) | `derivations.maintenance_capex` existe (`derivations.py:337`) y **ninguna de las 6 capas lo llama** — verificado leyendo `base_ratios.py`, `evolution.py`, `forensic.py`, `dividend.py`, `stress.py` y `synthesis.py` enteros | se declara en «Alcance» |
| Deuda con leases | `derivations.total_debt_incl_leases` (`:57`) tampoco tiene consumidor en las 6 capas | ídem |
| Comparación sectorial | el sector sólo elige umbrales (`thresholds/seed.py:56-61`); no hay peers | ídem |
| Restatements en el dictamen | el motor lo declara pendiente (`synthesis.py:210-211`) | ídem |
| Brecha básicas vs diluidas (`excel:146,151`) | ninguna métrica consume `shares_diluted` | se pintan las dos filas juntas en la pestaña 1 y se dice que la brecha no se calcula |
| **Paridad móvil** | esta fase es web + backend | follow-up explícito, como PHASE-43 |

---

## 7. Discrepancias entre los umbrales del Excel y los del motor

Mandan **los del motor**; el usuario decide si quiere cambiarlos. La tabla se
imprime **en pantalla**, junto a cada familia — es deuda de comunicación, no de
código.

| # | Concepto | Cuaderno | Motor | Naturaleza | Recomendación |
|---|---|---|---|---|---|
| 1 | Ratio corriente (L1) | mínimo 1 · ideal **1,5–2** (`excel:203`) | `higher_better` 1,0 / 1,5, **sin techo** (`base_ratios.py:61`) | el cuaderno acota por arriba (exceso de circulante ocioso) | **Documentar**. Cambiar a `band` implicaría pintar en ámbar empresas con mucha caja; no compensa |
| 2 | Prueba ácida (L2) | mínimo **0,8** · óptimo **1,5** (`excel:204`) | 0,7 / **1,0** (`base_ratios.py:62`) | difiere en **los dos** cortes | **Documentar**. El motor es más permisivo en ambos; si el usuario quiere su criterio, es una fila de `scoring_thresholds` |
| 3 | Ratio de caja (L3) | mínimo **0,2** · óptimo 0,3 (`excel:205`) | **0,15** / 0,3 (`base_ratios.py:63`) | sólo la alarma | **Documentar**; diferencia menor |
| 4 | Ratio de deuda (S1) | **banda 50–70 %** (`excel:233`) | `lower_better` 0,6 / 0,75 (`base_ratios.py:89-91`) | el cuaderno penaliza también **poca** deuda | **Documentar**. Cambiar a `band` es un cambio de fórmula → `ENGINE_VERSION` |
| 5 | Cobertura de intereses (S2) | óptimo **> 5** (`excel:237`) | `low_alarm=3`, `low_ok=**6**` (`base_ratios.py:92`) | el motor es **más exigente** | **Documentar**; a favor del usuario |
| 5b | …y su numerador | «beneficios antes de impuestos / gastos por intereses» (`excel:245`) | `ebit_clean / interest_expense` (`base_ratios.py:403-406`) | numerador distinto | **Documentar** en la nota de S2 |
| 6 | Deuda / EBIT | **no más de 3,5 × EBIT**, con **deuda total** (`excel:191,193`) | **S4b** = deuda **neta** / EBIT limpio, `high_ok=3`, `high_alarm=**5**` (`base_ratios.py:97-107`) | **divergen numerador y corte** | **Documentar como divergencia junto a S4b.** ⚠ **NO** emparejar con S4 (`high_alarm=3.5`, `base_ratios.py:94-95`): S4 es sobre **EBITDA**; la coincidencia del 3,5 es del número, no de la métrica |
| 7 | Intereses ≤ **20 % del EBIT** (`excel:190`) | — | equivale a S2 ≥ 5; el motor pide ≥ 6 | **Documentar** como equivalencia, sin métrica nueva |
| 8 | Margen bruto (R1) | óptimo **40 %** (`excel:255`) | **sin banda** (`base_ratios.py:131`) | el motor no lo acota | **Documentar**. Si el usuario lo quiere en semáforo, es un umbral por sector, no global |
| 9 | Margen neto (R4) | óptimo **10 %** (`excel:256`) | **sin banda** (`base_ratios.py:134`) | ídem | ídem |
| 10 | ROE (R5) | óptimo **12 %** (`excel:258`) | `low_ok=0.12` (`base_ratios.py:135`) | **coinciden** | Imprimirlo como coincidencia; da confianza en la tabla |
| 11 | Rotación de activos | «> 1» (`excel:261`) y además «(Activos/Ventas)×365» (`excel:216`) | A4 = ventas / activo medio, **sin banda** (`base_ratios.py:81`) | el cuaderno usa **la magnitud inversa** en la hoja 7 y la directa en la 9 | **Documentar la inversión de magnitudes**; no son comparables sin invertir |
| 12 | Apalancamiento financiero | **≤ 3** (`excel:259`) | `DUPONT_EM`, sin banda **y fuera del catálogo** (`base_ratios.py:262`) | ni banda ni etiqueta | **Añadir `DUPONT_EM` al catálogo** (sin `direction` → 0 filas nuevas de seed) y documentar la ausencia de banda |
| 13 | DPO «cuanto más bajo mejor» (`excel:219`) | — | A3 sin banda (`base_ratios.py:80`) | el propio cuaderno anota que el criterio es discutible (`excel:221-223`) | **Documentar**; no bandear |

---

## 8. Entregas incrementales

Rama única `feat/phase-44.9-investment-analysis-report`, commits por entrega
(`tipo(scope): descripción — Refs: PHASE-44.9`).

### E1 — Contrato: el backend deja de guardarse el porqué *(backend)*

**Alcance**: BLOQUEANTES 1a, 1b, 2, 3 + `runs/latest` + `ENGINE_VERSION` 1.1.0 +
`endpoints.md` + la única migración.

**Criterios de aceptación**

1. `GET /investment/analysis/metrics` devuelve **51** entradas y
   `[.[] | select(.direction != null)] | length` → **40**.
2. Test que afirma `set(keys servidas) == set(ALL_METRIC_KEYS)` — si alguien
   añade una métrica al engine sin catálogo, CI falla.
3. Toda entrada trae `label` no vacío, `family` ∈ las 7 familias del catálogo y
   `unit` ∈ el enum cerrado. Test parametrizado sobre las 51.
4. `GET /investment/fundamentals/items` devuelve **49** entradas con `label` ES y
   `group` ∈ {balance_current, balance_noncurrent, balance_liab_current,
   balance_liab_noncurrent, equity, income_*, cashflow_*}; el conjunto de `key`
   coincide exactamente con `CANONICAL_ITEMS` (test).
5. Un run nuevo trae `thresholds_used` con **una entrada por cada clave banded**
   del juego cargado, y `thresholds_hash(thresholds_used) === run.thresholds_version`
   (test de ida y vuelta).
6. `run.verdict.questions[]` trae `signals[]`, `evaluated_count` y
   `unavailable_count`. Test: para un valor con `is_financial=true`, la pregunta
   `accounting` sale con `evaluated_count == 0` en las señales de banda.
7. `GET /investment/analysis/{id}/runs/latest` devuelve la misma forma que
   `GET /analysis/runs/{run_id}` (test que compara ambas respuestas) y **404** si
   no hay runs.
8. `ENGINE_VERSION == "1.1.0"` con su entrada de historial en `version.py`, y un
   golden test que **falla** si el output del engine cambia sin mover la
   constante.
9. `alembic upgrade head` y `alembic downgrade -1` reversibles;
   `alembic heads` devuelve **una** línea; `alembic check` sin drift.
   *(Ver `lessons.md` [PHASE-44.1]: el padre se toma de `alembic heads`, nunca
   del nombre del fichero.)*
10. `internal_docs/api/endpoints.md` documenta los **28** endpoints del módulo
    (25 actuales + 3 nuevos); `grep -c investment` > 0.
11. `.venv/Scripts/python.exe -m pytest`, `ruff`, `black --check`, `mypy app/`
    verdes **con el intérprete del proyecto** (`lessons.md` [PHASE-44.6]).

### E2 — Esqueleto: hero + 6 pestañas en la URL + pestaña Veredicto *(web)*

**Alcance**: `ui/tabs.tsx`, `ui/segmented.tsx`, reescritura de
`analysis/[securityId]/page.tsx`, hero, pestaña 6 completa (dictamen + confianza
y datos), `flag-list`, `signal-table`, `degraded-panel`, `Skeleton`/`ErrorState`;
retirada de `analysis-report.tsx` y `metrics-card.tsx`.

**Criterios de aceptación**

1. Abrir `/investments/analysis/<id>` **sin** `?tab=` aterriza en
   `?tab=veredicto` y pinta el informe **sin pulsar «Ejecutar análisis»**,
   leyendo `runs/latest`.
2. **F5 (recarga dura) en cualquier pestaña conserva el informe y la pestaña.**
   Es el criterio que mata `page.tsx:122`.
3. Compartir la URL `?tab=veredicto&sub=datos` a otra sesión del mismo usuario
   reproduce la misma vista.
4. Con `run.verdict.safety_profile.label === 'watch'`, el checklist muestra las
   **5** condiciones de Conservador con ✔/✘ y el valor de las que son métricas.
5. Ninguna señal se imprime en snake_case: test de render con una
   `B4_dividend_funded_externally` → aparece el `message` de `run.flags`, no la
   clave.
6. Con `contribution_margin === null` el bloque de stress muestra **3**
   escenarios (ST2) y un aviso redactado por la UI; nunca 6 huecos mudos.
7. El bloque de stress lleva el rótulo «sobre caja libre (CFO − capex)».
8. `run.thresholds_version` se imprime **completo** (64 chars), no truncado.
9. La matriz de cobertura declara su fuente (`/statements`) y avisa si los
   ejercicios difieren de `run.years_covered`.
10. `pnpm knip` verde tras borrar `analysis-report.tsx`/`metrics-card.tsx`
    (`lessons.md` [PHASE-43]).
11. A 360 px de ancho: **cero scroll horizontal de página**; la barra de pestañas
    scrollea o colapsa a `<select>`.
12. `pnpm lint && pnpm typecheck && pnpm test` verdes.

### E3 — Los números: pestañas Estados y Ratios *(web)*

**Alcance**: `year-matrix.tsx`, `metric-line.tsx`, `metric-index.ts`, conmutador
€/%/Δ, tabla de divergencias del §7, `quality_flags` en la pestaña 1.

**Criterios de aceptación**

1. La pestaña Ratios pinta **las 27** métricas de capa 1 en **N columnas** (una
   por ejercicio de `run.years_covered`), no sólo la última.
2. Un margen de 0,42 se lee **«42 %»**; un DSO se lee **«45 días»**; S2 se lee
   **«6,8×»**. Test unitario del formateador por `unit`.
3. Cada celda con banda muestra su chip; el ejercicio que alimenta el dictamen
   va marcado.
4. Cada métrica muestra su corte al lado (de `run.thresholds_used`), y una
   métrica **sin banda** sale en **gris con la leyenda «sin banda absoluta»**,
   nunca en verde.
5. **MCD**: la sub-pestaña Actividad muestra **5 filas**, de las cuales A2/A3/A5
   dicen **visiblemente** «falta la partida 'cogs'» (no en `title=`).
6. **Realty Income**: la sub-pestaña Liquidez muestra L1/L2/L3 no calculables con
   la razón de `current_assets`, y L4 con valor; la barra de nivel 2 marca la
   sub-pestaña como degradada antes de abrirla.
7. La vista «% común» de Resultados avisa de que **4 de 16** partidas no tienen
   peso y de que el flujo de caja no está cubierto.
8. Las banderas de cuadre (`balance_identity_unverifiable` en los 8 ejercicios de
   MCD) aparecen en la pestaña Estados.
9. La tabla de divergencias del §7 se pinta bajo cada familia, y la fila del
   3,5 × EBIT apunta a **S4b**, no a S4.
10. `metric-index` sustituye a `findMetric`: 0 llamadas a `Array.find` por fila
    (revisión de código; no hay criterio automático).

### E4 — Las señales: Evolución, Forense y Dividendo *(web)*

**Alcance**: `score-breakdown-card.tsx`, pestañas 3, 4 y 5.

**Criterios de aceptación**

1. Las 8 tarjetas forenses se pintan **siempre**, con valor+banda+razón; el
   desglose aparece sólo cuando existe, y las 4 claves que nunca lo emiten lo
   declaran («este score no tiene desglose por diseño»).
2. Un score `not_computable` por falta de t−1 muestra la razón del motor («sin
   ejercicio N−1 no hay variación interanual que comparar»), distinta de «no
   tiene desglose».
3. Con `is_financial=true` la pestaña Forense es un `degraded-panel` con la
   razón literal `"modelo no aplicable a financieras"` y la consecuencia sobre el
   perfil.
4. La pestaña Dividendo muestra **12** filas en la matriz y **T2/T3 en el bloque
   Trayectoria**, nunca como filas con N−1 huecos.
5. D6 en no-REIT muestra «solo aplica a socimis (is_reit=false)».
6. D8 se rotula **«Margen de seguridad»** (del catálogo, no hardcodeado):
   `grep -rn "Rentabilidad por dividendo" apps/web` → 0 resultados.
7. `grep -rn "F5 — deuda emergente\|F6 — dilución" apps/web` → 0 resultados.
8. Las banderas se agrupan por `key`: un REIT con 7 emisiones de `C6_dilution`
   muestra **una** tarjeta con el rango de años.
9. La pestaña Evolución separa banderas «que mueven el veredicto» de las **10**
   que no están cableadas a ninguna pregunta.
10. Con una serie de **1** ejercicio, la pantalla enumera qué muere (E1 sin CAGR,
    E3, T3, m_score/f_score/F6/F7) en vez de mostrar huecos.

---

## 9. Riesgos y trampas conocidas (de `internal_docs/lessons.md`)

1. **[PHASE-43] «Una premisa escrita en un comentario caduca en silencio».** Es
   *exactamente* el origen de F5/F6/D8: alguien escribió las etiquetas a mano
   cuando eran ciertas y el catálogo se movió debajo. **Mitigación**: E1 mueve la
   fuente a la API; E4 lo verifica con greps que dan 0.
2. **[PHASE-34] «Cuando parcheas la misma raíz ≥2 veces, mueve la fuente de
   verdad».** Tres etiquetas ya divergieron. No se corrigen a mano: se retira el
   mecanismo que las permite (hardcodeo).
3. **[PHASE-43] «`tsc` y ESLint NO ven el código muerto».** Al retirar
   `analysis-report.tsx` y `metrics-card.tsx`, correr `pnpm knip`; y **antes de
   borrar**, grep de consumidores en `apps/web` **y** `apps/mobile` —
   **[PHASE-41] «No clasifiques código para borrar por su módulo/nombre»**. El
   móvil tiene shell de inversión desde 44.7 (según README; **no verificado por
   mí en esta sesión**).
4. **[PHASE-43] «Un hallazgo de código muerto es una hipótesis, no un
   veredicto»** y su corolario: si un símbolo huérfano dice ser fuente de verdad,
   es una **regresión, no basura**. Aplica a `maintenance_capex` y
   `total_debt_incl_leases`: se reportan, **no se borran**.
5. **[PHASE-44.6] «La forma de salida se PRUEBA, no se deduce leyendo el
   código»**, sobre todo si el desajuste falla en silencio. El JSONB del run no
   tiene contrato en Pydantic (`dict[str, Any]`, `analysis/schemas.py:48-53`): un
   cambio de forma no lanza excepción, simplemente deja la pestaña en blanco.
   **Mitigación**: un test que recorra la respuesta **HTTP real** y afirme la
   presencia de `evolution.horizontal`, `scores_detail.forensic.breakdowns`,
   `dividend_analysis.dps_series` y `verdict.stress.scenarios`.
6. **[PHASE-44.6] «`getattr(obj, "metodo")` sin llamarlo es SIEMPRE truthy».**
   Versión frontend: `band === null` **no es** falsy-igual-a-sano, y
   `status === 'approximation'` **no es** `ok`. La regla D4(c) y D4(f) existen
   por esto.
7. **[PHASE-44.6] «Verificar con el intérprete equivocado da un verde que no
   vale».** Backend con `backend/.venv/Scripts/python.exe`, no el `python` del
   PATH.
8. **[PHASE-44.1] «El padre de una migración se elige por el HEAD real del
   DAG».** `alembic heads` antes de fijar `down_revision`; una sola cabeza
   después.
9. **[PHASE-23.1] «No metas dos responsabilidades ortogonales en el mismo
   enum».** `thresholds_used` va en su propia columna, no colgando de `verdict`.
10. **[PHASE-37] «Un dedup por la clave equivocada over- y under-excluye a la
    vez».** Aplica al cruce señal ↔ métrica: emparejar por **etiqueta** está roto
    (6 divergencias verificadas en §3.6) y por clave hoy es imposible. Por eso
    BLOQUEANTE 3 y no una heurística.
11. **[ui-diagnosis] «Un "cambio visual regresó" es zoom del navegador hasta que
    un `git diff` demuestre lo contrario».** Durante la prueba manual: `Ctrl+0`
    antes de reportar densidades raras.
12. **Riesgo propio de esta fase — el volumen del JSONB.** `to_json_safe`
    serializa **todos** los campos de cada dataclass sin lista blanca
    (`serialization.py:31-32`) y `evolution.vertical` son 35 puntos × N años. Con
    10 ejercicios el run pesa. Si la respuesta se vuelve lenta, la salida **no**
    es filtrar en el serializador (rompería la trazabilidad), sino paginar o
    partir el endpoint. Medir antes de tocar.
13. **Riesgo propio — tests del backend.** La suite comparte una sola BD
    `crisol_test`: nunca dos `pytest` a la vez.

---

## 10. Definition of Done

Siguiendo `internal_docs/development-spec.md` §6, adaptado a que el usuario
publica por **push directo a `main`** (no PR):

- [ ] Código en la rama `feat/phase-44.9-investment-analysis-report`, mergeado a
      `main`.
- [ ] `make verify` verde en local: `pnpm lint && pnpm typecheck && pnpm test &&
      pnpm knip` + `cd backend && .venv/Scripts/python.exe -m pytest && ruff
      check . && black --check . && mypy app/`.
- [ ] `alembic upgrade head` / `alembic downgrade -1` reversibles ·
      `alembic heads` = 1 línea · `alembic check` sin drift.
- [ ] `internal_docs/phases/phase-44.9-investment-analysis-report.md` creado
      (as-built, con lo que cambió respecto a este plan).
- [ ] `internal_docs/README.md` con la fila 44.9 marcada ✅.
- [ ] `internal_docs/api/endpoints.md` con los **28** endpoints del módulo — es
      la primera vez que el módulo aparece ahí, así que cubre también la deuda de
      44.7/44.8.
- [ ] `internal_docs/data-model/schema.md` con la columna
      `analysis_runs.thresholds_used`.
- [ ] `internal_docs/lessons.md` actualizado si aparece un error evitable.
- [ ] ADR si se cambia algún umbral por el del cuaderno (§7) — cambiar una banda
      es cambiar el veredicto, y eso se decide por escrito.
- [ ] **Prueba manual, con los tres valores del golden**: MCD (`cogs` ausente,
      patrimonio negativo), Realty Income (REIT, balance no clasificado, Z''
      etiquetado sin calibrar) y JNJ. Para cada uno: recorrer las 6 pestañas,
      recargar en cada una, y comprobar que **ninguna** métrica ausente aparece
      como hueco mudo.
- [ ] Prueba manual del caso financiera (marcando un valor `is_financial`): el
      hero pinta **gris** en «¿La contabilidad es de fiar?», no verde.
- [ ] `internal_docs/investment-module-guide.md` actualizada con el playbook de
      la pantalla nueva.
- [ ] Commits en inglés con `— Refs: PHASE-44.9`; documentación en español.
- [ ] **No commitear hasta que el usuario haya probado la UI y dé el visto
      bueno.**

---

**Fichero sugerido**:
`internal_docs/improvements/phase-44.9-investment-analysis-report.md`