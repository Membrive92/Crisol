# PHASE-44.24 — Capa de legibilidad del informe · Plan de implementación

**Estado**: 📋 plan aprobado — las siete decisiones de §8 están tomadas por el
usuario (2026-08-27). Contrastado contra el código el 2026-08-26 y sometido a
dos rondas de revisión adversarial (§10)
**Manda sobre**: [`phase-44.24-report-legibility.md`](phase-44.24-report-legibility.md)
(el documento de alcance del usuario) en todo lo que aquí se corrige; el
alcance y los principios P1–P5 de aquel documento siguen vigentes.
**Depende de**: 44.9 · 44.16 · 44.17 · 44.20 · 44.21 · 44.22 · **44.23
(glosario)** — ver §0.1: es la dependencia que el documento no sabía que tenía.

Este plan hace tres cosas: (1) contrasta cada punto del alcance con lo que el
código YA hace, porque cuatro de ellos están construidos y uno cambia de
naturaleza; (2) decide DÓNDE vive cada pieza nueva, que es lo que determina si
hay que mover `ENGINE_VERSION` y si móvil hereda por construcción; (3) ordena
las entregas con sus paradas, sus tests y su verificación rompiendo el
código. Una revisión adversarial de cinco lentes le encontró 41 hallazgos; los
26 altos y medios se verificaron uno a uno (§10) y están integrados. Donde el
plan original decía una cosa y el código otra, aquí manda el código.

---

## Progreso (2026-08-27)

**Entrega A cerrada** — su phase doc está en [`phases/phase-44.24.A-meaning-layer.md`](../phases/phase-44.24.A-meaning-layer.md).

| Paso | Estado |
|---|---|
| **Parada 0** | ✅ salvo los commits. Ruido cosmético revertido (13 ficheros de `packages/types` que sólo cambiaban fin de línea o reformateo suelto), `HANDOFF.md:10` corregido —afirmaba cuatro entregas commiteadas cuando sólo hay tres—, y Dec.A aplicada: los dos documentos renombrados a 44.24. **Los tres commits están preparados y NO ejecutados**: la regla del proyecto es probar antes de commitear, y las tres entregas siguen pendientes de prueba manual |
| **A.0** — la forma que no mueve la huella | ✅ **verificada empíricamente**, no razonada: con `NamedTuple` el gate de `ENGINE_SHAPE_FINGERPRINTS` da verde; convertido a `@dataclass` a propósito, se cae con otro hash. La alternativa «definirlo en `presentation/`» queda descartada por el ciclo de imports |
| **A.3** — fichas de score y sus 27 variables | ✅ `engine/score_help.py` + 4 gates nuevos + endpoint `GET /investment/analysis/help` + tipos + hook + índice puro en `packages/ui` + la tarjeta de desglose consumiéndolo |
| **A.2** — `FLAG_HELP` (20 banderas) | ✅ las 20 con `what/why/reading/how_to_verify`, escritas contra su regla · 2 gates nuevos (cobertura en las dos direcciones y calidad por campo) verificados rompiéndolos · el endpoint sirve `flags` y la lista de banderas del veredicto gana su `ⓘ` con **dónde comprobarla en las cuentas**, que es lo que la separa de un oráculo |
| **C** — distancia · orden · procedencia | ✅ paquete puro `presentation/` + `report` en la API + `SignalTable` ordenada con distancia y procedencia · 10 sondas · gate de pureza que ahora SÍ ve el reloj. Doc en [`phases/phase-44.24.C-signal-gradient.md`](../phases/phase-44.24.C-signal-gradient.md). C.4 cerrada: cada señal enlaza con la fila que la produce (`hrefForSignal`), la fila de destino se resalta y se lleva a la vista, y `metric: null` se borra al cambiar de pestaña — sin eso el resaltado sobrevivía a la navegación y reaparecía en cada visita, que es lo contrario de lo que un resaltado significa |
| **A.1** — `METRIC_HELP` a `what/why/reading` (64) | ✅ 64 fichas escritas por 10 redactores leyendo su fórmula + 10 auditores (**41 correcciones**) · `MetricHelp` NamedTuple · gate por campo · `helpParagraphs` compartida y las dos apps pintando los tres tramos. Sin pérdidas de matiz respecto al texto anterior (comprobado) |
| **Parada A** — revisión de tono | ✅ aprobada por el usuario el 2026-08-27 sobre las fichas de score |
| **M** — motor 1.7.0 | ✅ `ThresholdSpec.origin` persistido (Dec.B) + la señal de stress de las financieras deja de puntuar (Dec.G) · huella registrada · 6 tests, 5 verificados rompiendo el código. Doc en [`phases/phase-44.24.M-threshold-origin.md`](../phases/phase-44.24.M-threshold-origin.md). **Corrección al plan**: `thresholds_version` NO cambia — `thresholds_hash` no incluye `origin` a propósito, y el plan afirmaba lo contrario |
| **B** — las frases del veredicto | ✅ `presentation/narrative.py` con las plantillas como DATO (hasheables y escaneables; con f-strings no lo serían), `NARRATIVE_VERSION` 1.0.0 y su huella del TEXTO · réplica del tri-estado en Python atada al fixture COMPARTIDO con vitest · 17 goldens de texto exacto · el titular y la frase por pregunta salen del servidor |
| **E** — lectura guiada | ✅ registro único de marcas (estaban en **tres** sitios con títulos ya divergentes, y **tres de las cinco** pestañas de matriz no pintaban ninguna leyenda) + gate de escaneo del fuente de los 4 emisores · guía «Cómo leer este informe» compartida, con los estados IMPORTADOS de donde se pintan · `SAFETY`/`DIVIDEND`/`safetyRules`/`CORE_ITEMS` a `packages/ui` (dedup de 2 copias, evitadas 2 más) · **paridad móvil completa** del hero y del veredicto · copy pass con `item_label()` y su gate sobre las 49 partidas |
| **F** — comparador de runs | ✅ `presentation/diff.py` PURO + `GET /runs/compare` + `thresholds_version` en el resumen + `diffRows()` compartida + sub-pestaña «Qué ha cambiado» en web y bloque plegable en móvil. `comparable` es **precondición**, no etiqueta. Arreglado el leak preexistente de móvil con `run.reset()`. **9 sondas, las 9 muerden** (dos no mordían: guardas solapadas y un fixture que llegaba al verde por otro camino) |
| **H** — auditoría UX (post prueba manual) | ✅ 33 defectos reales de 41 brutos, seis lentes + verificación a mano de los 27 que los escépticos no llegaron a mirar. Los grandes: 21 señales del veredicto enlazando a la MISMA pestaña (`locateMetric` inventaba destino), prosa sin acotar en ~25 sitios, buscador a 720 px, dictamen que imprimía el sidebar, móvil desmontando la pantalla al elegir un run. Doc en [`phases/phase-44.24.H-ux-audit-fixes.md`](../phases/phase-44.24.H-ux-audit-fixes.md) |
| **G** — dictamen imprimible | ✅ `@media print` (no había NINGUNA en la app) + `?print=1` con cabecera de `run.id` y las tres versiones + `data-print` declarado por los componentes · knip limpio · phase docs |
| **D** — nivel + dirección | ✅ `sparklineOf` y `scoreBreakdownRows` puros en `packages/ui` · columna «Tendencia» en las cinco matrices de las DOS apps · móvil gana el desglose de scores, que **no tenía ninguno** (27 variables invisibles) · 19 tests · **7 sondas, las 7 muerden** |

### Lo que salió del camino en A.3

- **`score-breakdown-card.tsx` imprimía la clave del motor** (`DSRI`,
  `P4_cfo_supera_beneficio`): el mismo defecto que 44.9 cerró para las señales
  del veredicto. Arreglado con el mismo mecanismo.
- **La regex de umbrales-en-prosa no cazaba un corte con signo.** Medido: el
  ejemplo del propio documento de alcance —«holgado del corte −2,22»— la pasaba
  entera. Ampliada con el signo y las pistas «del corte», «corte de», «umbral
  de», y re-apuntada a nivel de módulo para que los tres glosarios compartan
  UNA versión. Las 113 definiciones existentes siguen pasando: sin falsos
  positivos.
- **El gate de componentes es un escaneo ESTÁTICO por AST**, acotado por
  función, y no una ejecución de `forensic.compute` como decía el borrador: el
  check de inventario sale del cómputo en los sectores sin inventario material,
  así que una fixture de una eléctrica habría dejado `C3` fuera del conjunto
  emitido **y** fuera de la ficha, con el test en verde y la variable sin
  documentar.
- **Los cuatro gates verificados rompiéndolos**, y uno de ellos se declaró
  «sonda no entra» en vez de contar como verde cuando `black` movió el patrón.

### Un error mío, y cómo quedó

Ejecuté `pnpm format`, que formatea `**/*.{ts,tsx,js,jsx,json,md,yml,yaml}` de
**todo** el repo: 584 ficheros tocados, incluidos `CLAUDE.md`, los README y las
skills. Revertido con la lista exacta de ficheros a conservar; el árbol volvió a
los 48 previstos. Lo que **no** se revierte son seis documentos de
`internal_docs/` que ya venían modificados por 47.E4/47.H y que ahora arrastran
el reformateo (`README.md` y `api/endpoints.md` son los peores: ~380 y ~344
líneas de ruido sobre 117 y 85 de cambio real). Es cosmético y no hay gate de
formato en CI ni en lint, pero engorda esos dos diffs. **Regla para el resto de
la fase: nunca `pnpm format` a secas — `prettier --write` sobre los ficheros
tocados.**

---

## 0. Lo que el documento de alcance da por hecho y el código dice otra cosa

El documento se escribió el 2026-08-23 y ese mismo día se construyó otra cosa
con el mismo número.

### 0.1 Ya existe una PHASE-44.23, y es la mitad de la entrega A

En el árbol de trabajo (**sin commitear**) hay una fase **44.23 — «Qué es cada
fila del informe»** ([phase doc](../phases/phase-44.23-report-glossary.md)) que
entrega exactamente el hueco (1) del diagnóstico del documento —«`MetricDefinition`
no tiene campo de significado»—:

| Ya construido en 44.23 (glosario)                                                                                 | Fichero                                                                                                                     |
| ----------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| 64 definiciones de métrica, junto a la fórmula                                                                    | `backend/app/modules/investment/analysis/engine/glossary.py` (`METRIC_HELP`)                                                |
| 49 definiciones de partida canónica                                                                               | `backend/app/modules/investment/fundamentals/glossary.py` (`ITEM_HELP`)                                                     |
| `MetricDefinition.help` como **`@property`** que lee del diccionario — no como campo del dataclass                | `engine/metrics.py`                                                                                                         |
| `help` en `MetricDefinitionResponse` y `CanonicalItemResponse`; `help?` opcional en los tipos TS                  | `analysis/schemas.py` · `fundamentals/schemas.py` · `packages/types/src/models/investment.ts`                               |
| `MatrixRow.help` + el botón `ⓘ` en web (una definición abierta a la vez) y tocar la etiqueta en móvil             | `packages/ui/src/investment-matrix.ts` · `apps/web/components/investment/help-toggle.tsx` · `year-matrix.tsx` (web y móvil) |
| Cuatro gates: cobertura en las dos direcciones, no tautológica, longitud 40–320, **ningún umbral escrito a mano** | `backend/tests/test_investment_engine_contract.py`                                                                          |

Consecuencias:

- **Numeración.** Dos fases no pueden llamarse igual. La etiqueta `PHASE-44.23`
  está en **17 ficheros de código** (11 con la forma `PHASE-44.23 —`), más el
  README, el HANDOFF y la phase doc — **todos sin commitear**, así que renombrar
  el glosario sería un `sed` antes de la Parada 0, no una edición histórica.
  **Decidido (Dec.A): esta fase es PHASE-44.24** (entregas 44.24.A–G más una
  entrega de motor, 44.24.M): el glosario ya tiene phase doc y fila en el README
  con su número, y esto sólo toca este plan y el doc de alcance — los dos ya
  renombrados.
- **El glosario se commitea PRIMERO**, y la receta no es de una línea (§6,
  Parada 0): su CÓDIGO es disjunto del resto del árbol, pero tres ficheros de
  docs (`README.md`, `HANDOFF.md`, `api/endpoints.md`) mezclan hunks del
  glosario con los de 47.E4 y 47.H-2ª —dos entregas que a su vez comparten siete
  ficheros de código y sólo pueden ir juntas—, y el HANDOFF afirma en su línea
  10 que «hay cuatro entregas commiteadas» cuando el último commit (`6627698`)
  es sólo docs.
- **La entrega A no crea el campo de significado: lo ESTRUCTURA.** `help` hoy es
  una cadena que ya mezcla _qué mide_, _cómo se calcula_ y _hacia dónde se lee_
  («…Más alto, más holgura»). Lo que falta es el **porqué** (sesgo
  tesis-dividendos) y separar la lectura para pintarla aparte. Detalle en §2.A.
- **El patrón `@property` sobre un diccionario no es un atajo: es la única forma
  que no mueve el motor.** `_engine_shape()` del test de contrato recoge **todo
  dataclass definido en cualquier módulo de `engine/`** (y `_literal_domains()`
  todo alias `Literal`). Añadir `what/why/reading` como campos de
  `MetricDefinition` —lo que el documento escribe literalmente— tumbaría la
  huella y obligaría a subir `ENGINE_VERSION` por metadatos. La regla vale para
  los TRES contenedores de ayuda (métricas, banderas, scores): §2.A.0.

### 0.2 Puntos del alcance ya construidos, y la paridad móvil medida

| Punto del alcance                              | Estado real                                                                                                                                                           | Qué queda                                                                                                                                                                                                         |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **E.1** «Veredicto como pestaña de aterrizaje» | Hecho: `DEFAULT_REPORT_TAB = 'veredicto'` en `packages/ui/src/investment-report-sections.ts:199`, leído por `page.tsx:44` y `analysis.tsx:62`                         | Nada. Se retira                                                                                                                                                                                                   |
| **E.5** «Hero ampliado»                        | **Web** ya pinta las cuatro preguntas con `BandDot` + tri-estado, `DIVIDEND[dividend_verdict]`, confianza, ejercicios y fecha (`analysis-hero.tsx:90-136`)            | Web: staleness compacto. **Móvil** (`analysis.tsx:180-183`): pinta ticker, perfil, confianza, `engine_version` y ejercicios — **sin** los cuatro puntos, el chip de dividendo, `thresholds_version` ni `run_date` |
| **E.6** «Confianza explicada»                  | **Web** ya imprime «X % = completitud Y % × frescura Z» con `imputed_core_count`, `days_stale` y la tabla de partidas núcleo (`ConfidenceSection`, `tab-verdict.tsx`) | Web: «qué la subiría». **Móvil: no existe la sección**                                                                                                                                                            |
| **C.3** «Procedencia del corte»                | Parcial: `effectiveThreshold` distingue `applies=false` (con motivo) y `model_variant='uncalibrated'` (`≠`)                                                           | Genérica vs sectorial vs calibración anterior; el run **no persiste el sector ni el perfil** (§2.C.3)                                                                                                             |

**La paridad móvil del Veredicto, medida** (`report-tabs.tsx:546-600`): el
`TabVerdict` de móvil pinta las preguntas (con `SignalList`/`LegacySignals`) y
`FlagList`, y **nada más**. Faltan respecto a web, y el documento no lo veía:
(a) el checklist del perfil de seguridad (4 reglas de Evitar + 5 de
Conservador), (b) las frases de stress con `breakeven_fcf_drop` y
`not_computable_reason`, (c) la tarjeta «Alcance: lo que este informe NO
cubre», (d) `thresholds_version` y `run_date` en el pie, (e) la sección de
confianza, y en el hero (f) los cuatro puntos y (g) el dividendo. Más (h) el
desglose de scores, que móvil no pinta en ninguna pestaña. **Ocho piezas**, no
dos: E las lista una a una (§2.E.5–6), porque el titular de B cita un perfil
cuyas reglas móvil no enseña.

### 0.3 Números que el documento tiene mal, y de dónde salen los buenos

Los gates se derivan del código, nunca de un número escrito aquí; los números
sirven para dimensionar la redacción (Parada A).

| Documento                                       | Código                                                                                                                                                                                                         | Fuente                                                                                                                                                   |
| ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| «seis reglas de honestidad» (P1)                | **nueve**: las 7–9 llegaron en 44.16/44.17                                                                                                                                                                     | docstring de `packages/ui/src/investment-metric-rows.ts`                                                                                                 |
| «18 banderas»                                   | **20 claves** en `FLAG_LABELS`                                                                                                                                                                                 | `engine/flag_catalog.py:22-44`                                                                                                                           |
| «~40 fichas de métrica»                         | **64** en el catálogo (42 con banda, 7 de valoración sin ella)                                                                                                                                                 | `catalog.ALL_METRIC_DEFINITIONS`                                                                                                                         |
| «~30 componentes de score»                      | **27**: M-Score 8 (`DSRI GMI AQI SGI DEPI SGAI LVGI TATA`) · Z'' 4 (`X1–X4`) · F-Score 9 (`P1_roa_positivo … P9_mejor_rotacion`) · C-Score 6 (`C1_beneficio_por_delante_de_caja … C6_activo_crece_mas_del_10`) | `engine/forensic.py` — las claves que `ScoreBreakdown.components/checks` emiten. **C3 sólo se emite en sectores con inventario** (`forensic.py:563-583`) |
| «≈14 plantillas: 4 × 3 estados + 2»             | **4 preguntas × 6 estados de evidencia** × **un modificador** «¿el run registró desenlaces por señal?» (los runs 1.1.0–1.4.0 tienen `signals` pero no `outcome` ni `clear_count`), más titular y «qué miraría» | `investment-run-version.ts` · `packages/types` (`outcome?`, `clear_count?`)                                                                              |
| «~60 razones en 12 módulos» (borrador anterior) | **61 puntos en 13 módulos**                                                                                                                                                                                    | `grep 'reason=\|_not_computable(\|Amount.absent('`                                                                                                       |

Tres hallazgos que el documento no menciona: **`score-breakdown-card.tsx:298-300`
imprime las claves de los componentes en crudo** (`DSRI`,
`P4_cfo_supera_beneficio`) — el mismo defecto que las señales en crudo de 44.9;
**el run real de JNJ es de motor 1.3.0**, no 1.6.0, y es el fixture natural del
modificador «sin desenlaces»; y en móvil **el resultado de un rerun de la
empresa A se muestra como informe de B**: `run` (la mutación) nunca se resetea
al cambiar de valor (`analysis.tsx:72,76,98-101`). Éste es un bug vivo, fuera
del alcance del documento; F.3 lo arregla de paso porque su selector de runs
heredaría el mismo leak.

---

## 1. La decisión que ordena todo lo demás: dónde vive la capa de presentación

El documento pide tres cosas «server-side, deterministas»: frases (B),
distancia y orden (C), diff de runs (F). Dónde se calculan decide si hay que
mover el motor, si los runs viejos las reciben, y si móvil las hereda.

### 1.1 Se calcula al LEER el run, no al escribirlo

Nuevo paquete **`backend/app/modules/investment/analysis/presentation/`**,
PURO con la disciplina de `engine/` (gate propio, §5), que recibe el **run
persistido** más lo que el servicio le pasa (el `Security` de hoy y la
resolución de umbrales de hoy) y devuelve la capa de lectura. **No se persiste.**

**Punto de enganche**: la serialización ocurre en el **router**
(`AnalysisRunResponse.model_validate(run)` en `router.py:89`, `:111`, `:129`) y
el servicio devuelve el ORM. Se escribe `build_run_response(db, run) ->
AnalysisRunResponse` en `analysis/service.py` (carga el `Security`, resuelve
`resolve_thresholds(sector, std, is_financial)` de hoy, llama a
`presentation.build_report(...)` y lo cuelga en `response.report`); las tres
rutas lo llaman. `list_runs` sigue devolviendo `AnalysisRunSummary` sin
`report`. La inyección de `RestatementFlag` para F vive en la misma frontera.

**Rehidratación**: `thresholds_used` llega como JSONB con los cortes en
**texto**, y con **escala 6** cuando la spec vino de la tabla (`Numeric(12,6)`
→ `"0.600000"`), mientras el catálogo lleva `Decimal("0.6")`.
`presentation/rehydrate.py` convierte cada spec a `ThresholdSpec` con
`Decimal(str)` — el código que `test_investment_analysis.py:322-336` ya escribe
a mano; se mueve aquí y ese test lo importa. **Nada de la capa compara cadenas.**
Y la suite del backend **no siembra la tabla** al ejecutar `run_analysis`
(el lifespan no corre bajo `ASGITransport`), así que cualquier test escrito
como los de hoy vería `"1.5"` y nunca `"1.500000"`: los fixtures de origen se
extraen de un `thresholds_used` REAL.

Por qué al leer y no dentro del run:

1. **La tabla contiene runs de todas las versiones del motor** ([PHASE-44.16]).
   Calculado al leer, el run de McDonald's (1.0.0) y el de JNJ (1.3.0) reciben
   su narrativa hoy, sin reejecutar, con plantillas que dicen lo que aquel motor
   no registró. Persistido, sólo lo tendrían los runs futuros.
2. **Cambiar una plantilla no puede exigir reejecutar el motor.** Con
   `NARRATIVE_VERSION` en la respuesta, un dictamen impreso (G) cita las tres
   versiones y sigue siendo reproducible.
3. **La presentación no toca el motor.** Ni B ni C ni F cambian un dataclass ni
   un `Literal` de `engine/`. Lo que el motor SÍ cambia va en una entrega
   propia y anterior (§2.M, motor **1.7.0**): el campo `origin` de cada corte
   (Dec.B) y la señal de stress de las financieras (Dec.G). Después de M, todo
   lo que la presentación necesita está en el run o lo pasa el servicio; para
   los runs anteriores a 1.7.0 la presentación deriva lo que falta y lo dice.
4. **Un solo cálculo para dos pantallas** (P4). La distancia viaja calculada;
   web y móvil la formatean con `formatMetricValue`. Dos implementaciones de la
   misma distancia son la forma canónica de divergir ([PHASE-48]).

### 1.2 Contrato: campos NUEVOS y OPCIONALES

No hay «versión de schema de API» en el módulo (el documento pide un «bump del
schema»): el contrato es que los campos nuevos son **opcionales** en TS, porque
un backend anterior no los manda ([PHASE-44.16]). `AnalysisRun` gana
`report?: ReportLayer`:

```ts
interface ReportLayer {
  narrative_version: string;
  threshold_profile: {
    // (C.3) el perfil de HOY, resuelto por el SERVIDOR
    effective: string; // 'financials' | 'utilities' | … | 'unknown'
    sector: SectorInternal;
    is_financial: boolean;
    is_reit: boolean;
  };
  headline: string; // perfil + dividendo en una frase (B)
  questions: ReportQuestion[]; // una por pregunta, mismo `key`
  next_checks: ReportCheck[]; // 0–3, ordenados por severidad (B)
}
interface ReportQuestion {
  key: string;
  evidence: 'evaluated' | 'no-evidence' | 'not-recorded' | 'not-audited';
  outcomes_recorded: boolean; // `clear_count` y `unchecked_count` presentes (≥ 1.5.0)
  sentence: string;
  signals: ReportSignal[]; // las de QuestionSignal, ENRIQUECIDAS y ORDENADAS (C)
}
interface ReportSignal {
  key: string;
  status: MetricStatus | null; // para imprimir `*` si es approximation (regla 3)
  severity_rank: number; // 0 = peor; orden TOTAL (C.2)
  distance: SignalDistance | null; // null: sin corte aplicable o sin número (C.1)
  threshold_origin: ThresholdOrigin; // (C.3)
}
type ThresholdOrigin =
  | 'generic'
  | 'sector'
  | 'financial'
  | 'table' // persistidos por el motor ≥ 1.7.0 (M)
  | 'earlier_calibration' // sólo runs < 1.7.0: derivado y no coincide con nada de hoy
  | 'uncalibrated'
  | 'not_applicable'
  | 'not_recorded';
interface SignalDistance {
  cut: string | null;
  unit: MetricUnit;
  abs: string | null; // en la unidad de la métrica
  rel: string | null; // abs / |cut|; null si el corte es 0 o la unidad es `score`
  side: 'inside' | 'outside';
  next_band: 'caution' | 'stressed'; // la banda que cruzaría (con cortes iguales NO es «ámbar»)
  next_cut_missing?: string; // motivo cuando no hay corte siguiente (S7 por debajo de 1)
}
```

La LOCALIZACIÓN (pestaña + sub-sección, C.4) NO viaja: es contenido de
pantalla y se deriva en `packages/ui` (§2.C.4). El TEXTO de la distancia lo
compone `packages/ui` por unidad: `percent`/`pp` en puntos («a 3 pp del
verde»), `times/days/years/count` con `rel` («2,1× dentro del rojo»), `score`
sólo en puntos absolutos («a 0,4 del corte») porque un `rel` sobre un corte de
−0,253 (FZ) no significa nada. Regla de formato con test por unidad (§5).

### 1.3 Lo que sigue viviendo en el engine: los TEXTOS estáticos

Significado de métricas, banderas y componentes de score (A) vive junto a la
fórmula. Viaja por los endpoints de catálogo que ya existen más uno nuevo
(§2.A).

---

## 2. Las siete entregas

### 2.A — Backend: la capa de significado

**2.A.0 — Regla única para los tres contenedores de ayuda** (`glossary.py`,
`flag_catalog.py`, el nuevo `score_help.py`):

- Ningún `@dataclass` y ningún alias `Literal` a nivel de módulo en ficheros de
  `engine/` para metadatos: `_engine_shape` recoge ambos (contrato `:76-106`).
  Los registros son **`typing.NamedTuple`** definidos en su propio módulo del
  engine (`is_dataclass` es falso; verificado). La alternativa «definirlo en
  `presentation/`» **se descarta**: `glossary.py` importándolo crearía
  `catalog → base_ratios → metrics → glossary → presentation → … → catalog`
  (ciclo con `catalog` a medio inicializar) e invertiría la dependencia. El
  gate de pureza (§5) afirma que ningún `engine/*.py` importa `presentation`.
- Los diccionarios se escriben **con la clave como clave del dict**, nunca como
  kwarg `key="DSRI"`: `_emitted_flag_keys()` escanea todo `engine/*.py` con
  `\bkey=["']…["']` y contaría los 27 componentes como banderas sin nombre
  (contrato `:148-170`).
- `test_la_forma_del_engine_no_cambia_sin_mover_engine_version` se ejecuta tras
  A.1, A.2 **y** A.3; el resultado esperado es que NO se mueva.

**Cambia**

1. `engine/glossary.py`: `METRIC_HELP: dict[str, MetricHelp]` con
   `MetricHelp(NamedTuple): what, why, reading`. `MetricDefinition.help`
   **devuelve `what`** (no `what + reading`: medido, 33 de las 64 lecturas
   actuales tienen menos de 40 caracteres — «Más alto, mejor.» es una lectura
   legítima — y la concatenación rompería el tope de 320 en los peores casos).
   `reading` y `why` se pintan como líneas propias del panel `ⓘ`.
2. `engine/flag_catalog.py`: `FLAG_LABELS` se conserva (lo lee `flag_label()` y
   la huella lo enumera); al lado `FLAG_HELP: dict[str, FlagHelp]` con
   `what, why, reading, how_to_verify` y las **mismas 20 claves**.
3. `engine/score_help.py` (nuevo): `SCORE_HELP` con ficha por score (las ocho de
   `forensic.METRIC_KEYS`, aunque cuatro «no tienen desglose por diseño») y
   **una entrada por componente con su etiqueta**, agrupadas POR SCORE (los 27).
   La etiqueta arregla el `{name}` crudo de `score-breakdown-card.tsx`.
4. Contrato: `MetricDefinitionResponse` gana `what/why/reading` (manteniendo
   `help`); nuevo `GET /investment/analysis/help` → `{flags, scores,
narrative_version, engine_version}` (un endpoint; un segmento, no colisiona
   con `/{security_id}/runs`). Tipos TS opcionales.
5. Web: `score-breakdown-card.tsx` etiqueta desde `scores`; `flag-list.tsx` gana
   `ⓘ` con `what/why/how_to_verify` (mismo `HelpButton`). Móvil: `FlagList`
   gana el toque-etiqueta de la matriz.

**No cambia**: ningún dataclass ni `Literal` de `engine/`; ningún valor;
`ENGINE_VERSION`.

**Gates** (en `test_investment_engine_contract.py`; sonda de cada uno en §5):

- Cobertura `METRIC_HELP` == catálogo, dos direcciones, **por campo**.
- Cobertura `FLAG_HELP` == `FLAG_LABELS`.
- `set(SCORE_HELP.scores) == set(forensic.METRIC_KEYS)` — en Python; no se lee
  `FORENSIC_KEYS` del TS (segunda fuente; `screen_coverage` ya ata TS ↔
  catálogo).
- **Componentes: escaneo ESTÁTICO por AST, acotado por función**: se parsea
  `forensic.py`, y para cada `FunctionDef` de `{compute_m_score→m_score,
compute_z_score→z_score, compute_f_score→f_score, compute_c_score→F7}` se
  recogen las claves `str` de todo `ast.Dict` — comparadas EXACTAMENTE, por
  score, con `SCORE_HELP[score].components`. Acotar por función no es opcional:
  un escaneo del módulo entero recogería `evidence={"model_variant": …}`
  (`forensic.py:719`). Es el enfoque que el contrato ya eligió para las banderas
  (`:162-166`): ejecutar el engine sólo destapa lo que la fixture ejercita.
- **Y** una prueba de ejecución que valida la FIXTURE: construida con el
  `_statement(...)` de `test_investment_engine_layers.py:117-165` (INDUSTRIALS,
  completo; **no** el de `test_investment_engine.py:66-140`, al que le faltan
  `sga_expense/ppe_net/retained_earnings/share_issuance` y daría `{}` para
  M/Z/F), con la precondición AFIRMADA en el test (`sector not in
NO_MATERIAL_INVENTORY and not is_financial`) y cardinalidades **8/4/9/6**. El
  lado exento del umbral no necesita fixture nueva:
  `test_investment_sector_calibration.py:286-305` ya prueba que una eléctrica
  pierde C3 — se extiende con `set(utility.checks) == F7_keys(SCORE_HELP) −
{C_SCORE_INVENTORY_CHECK}` para atar el hueco al catálogo.
- Calidad por campo: `what` 40–320 + no tautológica + sin umbral en prosa;
  `reading` **10–200** + sin umbral (aquí es donde más importa); `why` 40–320 +
  sin umbral + **solape de tokens con `what` < 60 %**; `how_to_verify` 20–320 +
  sin umbral. La regex de umbrales (`:240-245`) se re-apunta de `d.help` a los
  campos **y se amplía**: hoy exige un dígito sin signo tras la pista y **el
  ejemplo del propio documento de alcance («−2,22») la pasa**; se añade signo
  opcional `[−-]?` y las pistas «del corte», «corte de», «umbral de».

**Parada A (contenido)**: 8 fichas completas (`L1 A1 S2 R4 m_score D2 Q1 E3`)

- 2 banderas (`C2`, `B4`) + el M-Score con sus 8 componentes → revisión de tono
  → resto en dos workflows de agentes con auditor por bloque, **cada bloque
  leyendo la fórmula**, y reportando cobertura por bloque (un bloque vacío es
  rojo, [PHASE-44.14]).

### 2.M — Motor 1.7.0: la procedencia se persiste y una financiera no puntúa stress

Entrega de motor, pequeña y ANTES de C y B, para que la capa de presentación
lea el campo definitivo y los goldens de la narrativa se escriban contra el
motor final. Un solo bump para dos cambios (Dec.B + Dec.G), y tus runs se
reejecutan una sola vez.

1. **`ThresholdSpec.origin`** (Dec.B): `Literal["generic", "sector",
"financial", "table"]`, con default `"generic"` en el dataclass para que
   los ~200 constructores existentes no cambien. Lo fija quien resuelve:
   `resolve_thresholds` en `sector_profiles.py` escribe `sector` cuando el
   perfil del sector sobreescribe el corte y `financial` cuando lo hace el
   perfil financiero (que se fusiona por encima, `:423-439`); y
   `thresholds/service.load_thresholds` escribe `table` cuando una fila de
   `scoring_thresholds` **difiere numéricamente** de lo que el engine
   resolvió — el seed es un espejo del engine, así que una fila distinta es
   una recalibración manual, que es exactamente lo que la tabla existe para
   permitir. Viaja en `thresholds_used` por `to_json_safe` sin tocar nada más.
2. **Stress en financieras** (Dec.G): `_question_resilience` recibe el
   `SecuritySnapshot` (como ya hace `_dividend_verdict`) y, cuando
   `_profile_key(security) == "financials"`, construye la señal como
   `_derived_signal("stress", "Escenario de stress", None, <motivo de
NOT_AUDITABLE>, "unchecked")`: `counted=False`, sin banda, así que no puede
   llegar en rojo ni a la `SignalTable` ni a `next_checks`. Las empresas sin
   dividendo ya devuelven cobertura `None` y no cambian.
3. **Versión**: `ENGINE_VERSION = "1.7.0"` con su entrada en el historial
   (dos motivos, escritos); la huella cambia (campo nuevo + `Literal` nuevo,
   los dos la mueven) y se registra su hash; `thresholds_hash` incluye el
   campo, así que `thresholds_version` de los runs futuros cambia — correcto y
   ya ocurrió en 44.10. Los runs guardados conservan el suyo y la UI les pone
   el aviso «motor anterior», que aquí es verdad.
4. **Tests**: `origin` correcto para una eléctrica (S4 → `sector`), una
   financiera clasificada en INDUSTRIALS (S3 → `financial`, no `sector`), una
   fila de tabla alterada a mano (→ `table`) y el genérico; y un banco con
   dividendo cuyo escenario de stress falla → señal `unchecked` con el motivo,
   veredicto de resiliencia `audited=False`, y **ninguna señal roja** en esa
   pregunta. Sonda: quitar la guarda de financieras → la señal vuelve a
   puntuar y el test cae.

### 2.C — Señales con gradiente y procedencia _(antes que B: B la consume)_

**2.C.1 Distancia** — `presentation/distance.py`, `distance_to_cut(value, spec)
-> SignalDistance | None`, especificada contra las formas REALES del catálogo:

- `higher_better`: dentro → corte `low_ok`; fuera → el siguiente corte hacia
  peor. `lower_better` simétrico.
- `band` **dentro** → el más cercano de los DOS cortes ok. `band` de un solo
  lado (S7: `low_ok=1, high_ok=2, high_alarm=3`, **sin `low_alarm`**): por
  debajo de 1 no hay corte rojo → `cut=null, rel=null, next_cut_missing="por
debajo de la banda no hay corte de alarma: poca deuda no es riesgo"`. Hoy
  ninguna señal de pregunta es `band`, pero la función promete el contrato y
  lo prueba.
- **Cortes iguales** (Q5 y T3: `high_ok == high_alarm`; T2:
  `low_alarm == low_ok == 0`): un solo corte, y `next_band` dice **`stressed`**
  — la región ámbar es vacía (`types.py:214-218`) y una etiqueta «a X del
  ámbar» nombraría una banda que no existe. Q5 es el caso de test.
- **Cortes negativos** (M-Score −2,22; FZ −1,036/−0,253): `rel = abs / |cut|`,
  nunca `abs / cut` — con el signo, un M-Score muy dentro del rojo tendría
  `rel` negativo y el orden lo pondría como el MENOS grave. Y para
  `MetricUnit.SCORE` **`rel = null`** siempre (un corte de −0,253 hace que
  `rel` explote sin significar nada); la UI enseña sólo `abs`.
- `None` cuando: sin banda, `applies=False`, `value=None` (banderas, derivadas,
  `not_applicable` con banda como L4) o `status` sin número. Corte 0 →
  `rel=null` con `abs`.
- **El test itera todas las specs** de `ALL_DEFAULT_THRESHOLDS` y de
  `resolve_thresholds()` para los 12 sectores × GAAP, con un valor en cada
  región — no una rejilla a mano que no contiene S7 ni Q5. Más una aserción
  que ata la premisa «las señales de pregunta siempre tienen distancia»: para
  toda clave de las listas de señales de `synthesis.py` (`:642-703`) con banda
  no nula, `distance` no es `None`.

**2.C.2 Orden** — `severity_rank` es un orden **TOTAL** definido en
`presentation/ordering.py` como `(band_rank, 0 if rel is None else 1,
signed_rel, key)`, con la decisión escrita en el docstring: **una señal sin
gradiente (bandera encendida, derivada, unidad `score`, corte 0) va ANTES que
una con gradiente en la misma banda** — es evidencia binaria, no un roce. El
centinela se ata a `rel is None`, no a `distance is None` (el corte 0 tiene
distancia sin `rel`). **Nunca se compara `None` con un número**: un `rel or 0`
pondría una B4 roja como «exactamente en el corte», la menos grave. Tests: B4
roja (`rel=None`) antes que D2 a 2,1×; corte 0 vs gradiente en la misma banda;
empate EXACTO (misma banda y `rel`) resuelto por clave.

**2.C.3 Procedencia** — `presentation/origin.py`, tras rehidratar. Con M
hecha, para un run ≥ 1.7.0 la procedencia **se lee**, no se infiere; la
derivación queda sólo para los runs anteriores, y lo dice:

1. Sin clave en `thresholds_used` → `not_recorded` = «**el run no registró el
   corte de ESTA métrica**» — no «pre-44.9»: un run 1.3.0 tiene
   `thresholds_used` y no tiene S7/S8. La UI dice entonces que el corte que
   enseña es **el del catálogo de hoy** (regla 5).
2. `applies=False` → `not_applicable`. ANTES de indexar ningún default.
3. `model_variant == 'uncalibrated'` → `uncalibrated`.
4. **Si la spec trae `origin`** (motor ≥ 1.7.0) → ése es el valor
   (`generic` / `sector` / `financial` / `table`). Fin.
5. **Si no lo trae** (run < 1.7.0), derivación: igual (como `Decimal`, los
   cuatro cortes) a `ALL_DEFAULT_THRESHOLDS[key]` de hoy → `generic`; igual al
   **perfil de hoy** que pasa el servicio → `sector`; **a ninguno →
   `earlier_calibration`** («cortes de una calibración anterior: vuelve a
   ejecutar para ver los actuales»). Con sólo dos salidas, cualquier
   recalibración genérica posterior al run se leería como «sectorial».
6. La ETIQUETA del perfil la emite el **servidor** (`report.threshold_profile`)
   con un helper puro `threshold_profile_key(sector, *, is_financial)` junto a
   `profile_for` en `sector_profiles.py`: `'financials'` si `is_financial or
sector is FINANCIALS`, si no `sector.value`. Componerla en la UI con
   `security.sector` es **falso para toda financiera clasificada en otro
   sector** (`profile_for` fusiona FINANCIALS por encima: `sector_profiles.py:423-439`)
   — y por el prefijo SIC 67 es el estado normal de las socimis, incluida la
   del usuario. Test: `INDUSTRIALS + is_financial=True` → `'financials'`.

Tests de origen: los ocho valores; un run 1.7.0 con `origin` presente NO se
deriva (sonda: cambiar un corte del fixture y comprobar que el origen no se
mueve); `sector` derivado con un solo corte distinto; **`"0.600000"` vs
`Decimal("0.6")` → `generic`** (fixture de un run real); `earlier_calibration`;
`applies=False` antes de indexar.

**2.C.4 Cross-links** — contenido de pantalla en `packages/ui`:

- **Un solo registro** `SECTION_PLACEMENT: {section, tab, sub}[]` en
  `investment-report-sections.ts` del que se derivan `allScreenMetricKeys()` y
  `locateMetric(key) → {tab, sub}`. Con una sola fuente, «toda clave resuelve»
  es cierto por construcción y **no es un gate**; los invariantes que sí pueden
  fallar: (a) todo `tab` emitido es clave de `REPORT_TABS`; (b) todo `sub` es
  la `key` de una sección real; (c) las derivadas `fcf_trend` → `evolucion` y
  `stress` → `veredicto` resuelven (están fuera de toda lista y el gate del
  backend no las ve). **Precedencia declarada**: `R4`, `A4` y `DUPONT_EM`
  están a la vez en `RATIO_FAMILIES` y en `DUPONT_SECTIONS`; gana la familia y
  se prueba con `R4`. La clave `'dupont'` (hoy local en `tab-ratios.tsx:25-28`)
  sube al fichero compartido.
- **Web**: `SignalTable` gana `hrefFor?: (signal) => string | null`, construido
  en `page.tsx` con `locateMetric` + `setParam`. **Ningún hook de
  `next/navigation` en `signal-table.tsx`/`tab-verdict.tsx`** — no porque
  `useSearchParams` lance (en Next 15 devuelve `null` fuera del App Router;
  `useRouter` sí lanza) sino porque produciría hrefs `"null?tab=…"` **sin que
  ningún test se cayera**; `tab-verdict.test.tsx:121-131` monta sin router.
  `YearMatrixProps.highlightKey?: string | undefined` + `useEffect` con
  `scrollIntoView` y `aria-current="true"` en la fila, temporizador local de
  2 s **que además borra `metric` de la URL** vía `setParam` (una URL
  compartida no debe re-resaltar); el prop llega a los **nueve**
  `<YearMatrix>` de `TabRatios/TabForensic/TabEvolution/TabDividend`
  (Estados no es destino). El scroll es un efecto post-montaje del destino:
  `TabPanel` devuelve `null` si no está activa (`tabs.tsx:163`). Y
  `handleTabChange` y los tres `onSubChange` patchean `metric: null`: `setParam`
  parte de `searchParams.toString()` y conserva lo que no toca (`page.tsx:79-89`).
- **Móvil**: no necesita `sub` (Ratios pinta todas las familias apiladas:
  `report-tabs.tsx:235-255`); sólo `{tab, highlightKey}`. `onNavigate?:
(target: {tab; metric?}) => void` es un **prop** de `TabVerdict`/`SignalList`
  (no de `TabContext`, para que `makeCtx` de `report-tabs.test.tsx:103` siga
  compilando); las filas son `Pressable` con `accessibilityRole="link"`.
  `analysis.tsx` gana `highlightKey` en estado y un `scrollRef` sobre el
  `ScrollView` de pantalla (`:96`); `onSelect` lo resetea; el `YearMatrix` móvil
  gana `highlightKey` + `onRowMeasured(key, y)` **medido con
  `measureLayout(scrollRef)`** — el `onLayout.y` de la fila es relativo a la
  columna de etiquetas, no al scroller — y la pantalla hace `scrollTo({y})` en
  un efecto; el resaltado se limpia al cambiar de pestaña.
- Si `highlightKey` no casa con ninguna fila (empresa sin dividendo enlazada
  desde D2): aviso «la señal X no se calcula en este análisis» (regla 6).

### 2.B — Frases-veredicto deterministas

1. `presentation/narrative.py` con `NARRATIVE_VERSION = "1.0.0"`. **Las
   plantillas son DATOS**: `TEMPLATES: dict[tuple[question, state], str]` con
   placeholders de `str.format`, más `HEADLINE_TEMPLATES` y
   `NEXT_CHECK_TEMPLATES`. No f-strings: no hay nada que hashear salvo el fuente
   del módulo (bump por cada comentario → gate ruidoso → ignorado,
   [PHASE-44.9]) ni nada que escanear. Huella = sha256 del `json.dumps` de las
   plantillas (el **texto**, no las claves) por `NARRATIVE_VERSION`, «sólo se
   comprueba la vigente». **Gate de prosa propio para plantillas**: tras quitar
   los `{…}`, el texto **no contiene ningún dígito** — la regex de A no caza
   «−2,22» ni «1,5» sin pista, y una plantilla sólo tiene números por parámetro.
   Lo que la huella NO ve (el código de composición, `format.py`) lo cubren los
   goldens; se escribe en el docstring.
2. **Estados y modificadores**: (pregunta × `evidence`) × `outcomes_recorded`:
   - `not-recorded` (< 1.1.0): parametrizada con `verdict` y las etiquetas de
     `red_signals`/`amber_signals` **verbatim** (son etiquetas, no claves:
     `synthesis.py:388-389` y la fixture real de MCD). Dice que el veredicto
     **no es auditable, no que no exista**: el borrador hacía que
     `not-recorded` sustituyera a `stressed` y escondía los dos rojos que 44.16
     rescató en McDonald's.
   - `outcomes_recorded=false` (1.1.0–1.4.0; el JNJ real): `healthy` NO dice
     «comprobadas y limpias» — regeneraría en prosa el falso limpio que 1.5.0
     quitó (el `reason` de entonces es literalmente «no se ha encendido»). Dice
     «N sin puntuar (el motor de entonces no distinguía limpias de no
     comprobables)», la misma rama que `evidenceBreakdown()` toma.
   - `not-audited` y `no-evidence`: además del porqué, **nombran las señales
     rojas/ámbar que sí puntuaron** (`_audit` conserva el veredicto:
     `synthesis.py:536-546`).
   - `evaluated` × banda: portantes + las dos peores por `severity_rank`, con
     valor formateado, corte y **`*` si `status == 'approximation'`** (regla 3).
3. `presentation/evidence.py`: réplica de `questionEvidence()` con **semántica
   de presencia de clave** (`'signals' in q`, `q['audited'] is False` — no
   `.get()` con truthiness, que colapsa ausente y `False`) **más**
   `outcomes_recorded = 'clear_count' in q and 'unchecked_count' in q` (la
   MISMA prueba que `evidenceBreakdown()`).
4. `presentation/format.py`: espejo de `investment-metric-format.ts` atado por
   fixture; la narrativa NO formatea distancias (las formatea `ui`).
5. «Qué miraría a continuación»: hasta 3 bullets de las señales ámbar/rojas
   con peor `severity_rank`, con la parte accionable de `reading`. Reglas:
   - Señales de preguntas **permanentemente no auditables** (`audited=false` y
     `load_bearing=()`) se **excluyen**: en un banco con dividendo,
     `_question_resilience` sigue añadiendo `_stress_signal` (`synthesis.py:704`)
     y puede salir roja aunque el motor se niegue a presentar la pregunta
     (`NOT_AUDITABLE`); el bullet «vigila el escenario de stress» contradiría el
     chip gris. Hoy la contradicción ya existe dentro de la `SignalTable`
     desplegable; el plan la ascendería a titular.
   - Señales de preguntas **temporalmente** no auditadas (`audited=false` con
     portantes) se **mantienen** con el prefijo «pregunta no auditada:» — una
     contabilidad sin M-Score pero con accruals en rojo es un hallazgo real.
   - **La causa raíz está en el motor y M la arregla** (Dec.G): con 1.7.0 la
     señal de stress de una financiera sale `unchecked` y no puede ser roja.
     La regla de exclusión de arriba se conserva igualmente, porque los runs
     anteriores a 1.7.0 siguen llevando la señal roja y la narrativa se
     calcula también para ellos.
   - **«Nada que vigilar» prohibido** si alguna pregunta es `not-recorded` o
     `not-audited`; cuando aplica, dice cuántas señales se comprobaron. En un
     run 1.0.0 los `next_checks` caen a las etiquetas rojas/ámbar registradas,
     marcadas «no auditable».
6. **Fixtures compartidos** en `packages/ui/src/__fixtures__/`
   (`question-evidence.json`, `metric-format.json`): el único sitio donde
   `vitest` (`include: src/**/*.test.ts`) y `pytest` (`Path(__file__).parents[2]`,
   como `screen_coverage`) los encuentran sin salirse del patrón. Las dos
   suites afirman el **recuento de casos** (≥ 12 cubriendo los cuatro estados;
   ≥ 8 unidades × signo × `null`), y que **ningún caso lleva `null` JSON** en
   `signals`/`evaluated_count`/`audited`: los runs persistidos nunca lo llevan
   (los viejos omiten la clave; los nuevos serializan `[]`/`0`), y un `null`
   haría que las dos suites tomaran ramas distintas. Un caso con `audited`
   ausente y `evaluated_count > 0` esperando `evaluated`, que caza una réplica
   con `audited` falsy.
7. Web y móvil pintan `sentence`, `headline` y `next_checks`. Ninguna app
   compone texto.

**Goldens**: `tests/test_investment_narrative.py` con fixtures **de la BD real**
(MCD 1.0.0, JNJ 1.3.0, O) y sintéticos para lo que los reales no cubren
(`not-audited`, `no-evidence` de una financiera, un portante `approximation`).
El de MCD afirma que **la etiqueta roja aparece en la frase del dividendo**.

**Parada B**: las plantillas con un ejemplo REAL de cada una, antes de los
goldens. Es la voz del usuario.

### 2.D — La dirección: series en las filas

1. `packages/ui/src/investment-sparkline.ts` (puro): `sparklineOf(series) →
Sparkline | null` con puntos normalizados, tendencia y **`ariaLabel`** por
   unidad. `null` con < 3 puntos con número.
2. `MatrixRow.spark?: Sparkline | null | undefined` — **tri-estado**: clave
   ausente = la fila no tiene columna de tendencia (Estados, `missingRow`,
   `dupontCheckRow`); `null` = «serie corta»; objeto = se dibuja. `metricRow()`
   la escribe como `...(hasSeries ? { spark: sparklineOf(series) } : {})`.
3. **La tabla decide la columna una vez**: `hasTrend = rows.some(r => r.spark
!== undefined)`. Puntos de edición: web `year-matrix.tsx` — `<th>` extra
   (`:63-71`), `<td>` con el `<svg role="img" aria-label>` o «serie corta», un
   `<td>` **vacío** para las filas sin la clave (si no, se desalinean), y los
   DOS `colSpan` (`:78`, `:168`) pasan a `years.length + 1 + (hasTrend ? 1 :
0)`; móvil `year-matrix.tsx` — cabecera (`:94-100`), filler de grupo
   (`:104-107`), celda con `height` fijo y filler vacío. `react-native-svg` es
   **dependencia DIRECTA** de `apps/mobile/package.json:39` — importa: con el
   linker aislado una peer transitiva no resolvería — y `jest.config.js` ya la
   transforma. Sin dependencia nueva.
4. D.2: `scoreBreakdownRows()` **se CREA** en `packages/ui` (hoy
   `score-breakdown-card.tsx:46-47` hace `Object.entries` inline), recibe las
   etiquetas de `/help` **por argumento** y produce delta vs ejercicio anterior
   - mini-serie desde `index.series(key)`. Móvil gana su `ScoreBreakdownCard`
     RN. Cero backend.

### 2.E — Lectura guiada y jerarquía

1. ~~E.1~~ retirada (hecha).
2. **«Cómo leer este informe»**: contenido en
   `packages/ui/src/investment-report-guide.ts`; los estados con las MISMAS
   etiquetas de `EVIDENCE_LABEL` y `bandLabel` importadas.
3. **Marcas y leyenda** — inventario real: leyenda de marcas sólo en Estados
   (`tab-statements.tsx:132-145`) y Ratios (`tab-ratios.tsx:87-101`, sin
   `·†≈≠`; `DuPontSection` sin leyenda); Forense usa el slot para la leyenda
   DERIVADA de huecos (`metricGapLegend`); Dividendo pasa una nota; Evolución
   nada. Y las marcas están definidas **tres veces** con títulos que ya
   divergen: `PROVENANCE_MARK`/`PROVENANCE_TITLE` (no exportados,
   `metric-rows.ts:40-59`), los literales `'*'` y `'≠'` inline (`:97`, `:112`),
   `provenanceMark()/provenanceTitle()` en `statement-rows.ts:173-185`, y el
   `•` del ejercicio del dictamen en las dos cabeceras de `year-matrix`. Plan:
   (a) **`packages/ui/src/investment-marks.ts`** exporta `MARK` con glifo Y
   título por entrada (`approximation:'*'`, `derived:'†'`, `imputed_zero:'·'`,
   `estimated:'≈'`, `uncalibrated:'≠'`, `verdict_year:'•'`) y lo consumen
   `metricCell`, `statementCell` (fuera la copia) y las dos cabeceras; (b)
   `MATRIX_LEGEND = Object.values(MARK)` más una `TEXT_LEGEND` aparte para los
   estados de texto (`—`, `n/a`, gris); (c) `YearMatrix` (web y móvil) gana
   `marksLegend?: LegendEntry[]` separado de `legend` — en móvil deja de ser
   `string` para que Forense pinte ambas sin concatenar; (d) las **cinco**
   pestañas de matriz la pintan (es trabajo: tres tabs y DuPont hoy no tienen
   nada). **Gate de efecto no tautológico**: «leyenda ⊇ MARK» se cumple por
   construcción; el test que vale escanea el fuente de los **cuatro** ficheros
   emisores (`readFileSync`, precedente `apps/web/app/period-preset-wiring.test.ts`)
   buscando `push('<un carácter>')`, `return '<un carácter>'` o `mark: '…'`
   fuera de `MARK`, con `expect(files.length).toBe(4)` contra la vacuidad.
4. **Glosario** (`/investments/analysis/glossary` web; sheet móvil) que
   renderiza los catálogos sin contenido propio (P2).
5. **Hero móvil a paridad**: cuatro `BandDot` con `questionEvidence` +
   `DIVIDEND[dividend_verdict]` + `thresholds_version` + `run_date` + staleness
   compacto. `DIVIDEND` y `SAFETY` suben a `packages/ui` — `SAFETY` está
   **duplicada** en `analysis-hero.tsx:10-14` y `tab-verdict.tsx:33-37`.
6. **Veredicto móvil a paridad** (las piezas de §0.2): (a) checklist del perfil
   con un view-model `safetyRules(profile)` en `packages/ui` que **sustituye**
   las `CONSERVATIVE_RULES`/`AVOID_RULES` escritas a mano de
   `tab-verdict.tsx:40-56` en las dos apps — no se copian a móvil; (b) frases
   de stress, `breakeven_fcf_drop` y `not_computable_reason` (el dumbbell sigue
   web, backlog 44.22); (c) tarjeta de alcance, cuyo texto pasa a una constante
   compartida; (d) `ConfidenceSection` con `statements`/`items` como **props
   de `TabVerdict`** (no en `TabContext`); `TabBody` los baja y `makeCtx` se
   actualiza. Web: «qué la subiría» derivado del run.
7. **Pasada de copy sobre razones** — dos inventarios: (a) motor: 61 puntos en
   13 módulos, clasificados en la phase doc como _de negocio_ / _técnica clara_
   / _de motor_; la mayor fuente de la tercera es **`Amount.absent`**
   interpolando la clave canónica — se traduce en origen con la etiqueta de
   `CANONICAL_ITEM_DEFINITIONS` (ya importado por `types.py`). (b) **UI**:
   `DegradedPanel`/`InlineNotice` en sus llamadores (`stale-run-notice.tsx:41-43`,
   `StressCard`, `ConfidenceSection`) — el alcance los pedía y el borrador sólo
   miraba el motor. **Sin bump** (Dec.F): la política de `version.py` es
   «fórmula o métrica nueva», la huella no cambia, y `isRunOutdated` compara
   también el PATCH (`investment-run-version.ts:105-123`): un 1.6.1 pondría el
   aviso «motor anterior» en **todos** los runs guardados por una frase. Nota
   indentada bajo 1.6.0 en el historial. Los tests que afirman razones son
   unitarios en tres ficheros (no goldens). **Parada (c)**: toda razón sin
   traducción evidente se pregunta.

### 2.F — Comparador de runs (misma empresa en el tiempo)

1. `presentation/diff.py` (puro): `diff_runs(base, target, restatements) →
RunDiff` sobre los dos payloads rehidratados: `comparable` (mismo
   `engine_version` y `thresholds_version`); `company_changes` sólo si
   comparable (bandas, banderas agrupadas, las 7 columnas de score, `verdict`
   por pregunta, `years_covered`); `method_changes` si no, etiquetadas «cambió
   el motor o la calibración» y **nunca** como cambios de la empresa (si además
   difieren los ejercicios, se dice que las causas se mezclan);
   `evidence_changed` con los campos crudos (la UI aplica `questionEvidence()`);
   `restatements` (persistidas con `detected_at`, `fundamentals/models.py:174-187`)
   entre las dos fechas, inyectadas por el servicio.
2. `GET /investment/analysis/{security_id}/runs/compare?base=<id>&target=<id>`
   (defaults último y anterior; 404 sin dos). Scoped por usuario.
3. **Dónde vive el run seleccionado**: web, `?run=<id>` y `?compare=<baseId>`
   vía `setParam` en la ruta existente. Precedencia: `activeRun = selected ?
selectedRun.data : (run.data ?? latestRun.data)` — **no**
   `run.data ?? selectedRun.data ?? …`: `useMutation.data` persiste mientras la
   página esté montada y el selector no podría enseñar nunca un run viejo tras
   un rerun. «Un rerun recién hecho gana» se consigue **borrando la selección**
   en el handler de rerun (`setParam({ run: null, compare: null })` en
   `onSuccess`). `queryKeys.investment.compare(securityId, base, target)` bajo
   `investment.all` (`keys.ts:198`) para que `useRunAnalysis` lo invalide.
   `AnalysisRunSummary` gana `thresholds_version` (una línea: `schemas.py:105`
   mapea por atributo y el ORM lo tiene) y `thresholds_version?: string` en TS,
   para etiquetar «comparable» sin N peticiones. **Móvil**: `selectedRunId` en
   estado y **`run.reset()` en `onSelect`** — arregla el leak preexistente de
   §0.3, que el selector heredaría. `useAnalysisRuns` existe sin consumidor: el
   hero gana el selector.
4. UI: web dos columnas + lista; móvil la lista; `diffRows()` en `packages/ui`.

### 2.G — Dictamen portable + cierre

1. Vista imprimible (`@media print`, hoy ninguna en `apps/web`) sobre Veredicto
   - `?print=1`; cabecera con `run.id`, las tres versiones, fecha y la tarjeta
     de alcance (constante compartida desde E.6). Web-only, marcado.
2. QA de contenido con el usuario; `NARRATIVE_VERSION` 1.0.0 definitivo.
3. `knip` (**sí** corre en CI: `ci.yml:52`) y barrido de lo que E deje huérfano
   (`CONSERVATIVE_RULES`/`AVOID_RULES`, leyendas por tab, `SAFETY` duplicada).

---

## 3. Qué se mueve de versión, y qué no

| Entrega | `ENGINE_VERSION` | Huella                                                           | `NARRATIVE_VERSION` | Contrato API                                                 | Migración |
| ------- | ---------------- | ---------------------------------------------------------------- | ------------------- | ------------------------------------------------------------ | --------- |
| A       | no               | no (NamedTuple + dicts, §2.A.0; gate ejecutado tras A.1/A.2/A.3) | —                   | + campos opcionales, + `/help`                               | no        |
| **M**   | **1.7.0**        | **sí** (campo + `Literal` nuevos; se registra el hash)           | —                   | `origin` en cada spec de `thresholds_used`                   | no        |
| C       | no               | no (`presentation/`)                                             | —                   | + `report.*` opcional                                        | no        |
| B       | no               | no                                                               | **1.0.0**           | + `report.narrative_version`                                 | no        |
| D       | no               | no                                                               | —                   | no                                                           | no        |
| E.7     | **no** (Dec.F)   | no cambia                                                        | —                   | no                                                           | no        |
| F       | no               | no                                                               | —                   | + `runs/compare`, + `AnalysisRunSummary.thresholds_version?` | no        |
| G       | no               | no                                                               | —                   | no                                                           | no        |

Cero migraciones. Un solo bump de motor en toda la fase, y va al principio.

---

## 4. Principios del documento, aplicados con el código delante

- **P1 (nueve reglas).** Las piezas nuevas se construyen ENCIMA de
  `metricRow`/`metricCell`. Tres regresiones nuevas en
  `investment-metric-rows.test.ts`: sparkline sobre `not_applicable` (sin banda
  dibujada), distancia sobre `applies=false` (`null`), narrativa sobre
  `not-recorded` (plantilla propia, con los rojos).
- **P2.** Métricas/partidas/banderas/scores → engine. Frases → `presentation/`.
  Guía, leyenda, marcas, reglas del perfil, tarjeta de alcance → `packages/ui`.
  Ningún literal en `apps/*`.
- **P3.** `presentation/` puro por AST (con gate de reloj, §5); **plantillas
  como DATOS (`str.format`) sobre campos del run**; sin LLM.
- **P4.** View-models en `packages/ui`; el servidor manda lo calculado. Se
  cierran **ocho** huecos de paridad preexistentes (§0.2). Excepción declarada:
  print.
- **P5.** Ningún score global, benchmark vivo ni frase de compra; el gate de
  «sin dígitos» recorre las plantillas.

---

## 5. Tests y gates — la tabla completa

| Qué                                 | Afirma                                                                                                                                                                                                                                                                                                                            | Dónde                                                                     | Sonda (rompiendo…)                                                                                                                             |
| ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ---- | --------------------------------------------------------- |
| Cobertura A por campo               | `METRIC_HELP` == catálogo, dos direcciones, ×3 campos                                                                                                                                                                                                                                                                             | `test_investment_engine_contract.py`                                      | `why=""` en L1 → cae el gate de longitud por campo (no «quitar `why`»: `TypeError` de import, rojo por la razón equivocada)                    |
| Cobertura banderas                  | `FLAG_HELP` == `FLAG_LABELS`                                                                                                                                                                                                                                                                                                      | ídem                                                                      | **quitar** una clave de `FLAG_HELP` (añadirla a `FLAG_LABELS` ya tumba `…no_tiene_entradas_muertas`)                                           |
| Scores                              | `SCORE_HELP.scores` == `forensic.METRIC_KEYS`                                                                                                                                                                                                                                                                                     | ídem                                                                      | quitar `F6`                                                                                                                                    |
| Componentes (estático, por función) | claves `str` de los `ast.Dict` de los cuatro `compute_*` == `SCORE_HELP[score].components`                                                                                                                                                                                                                                        | ídem                                                                      | renombrar `SGAI`                                                                                                                               |
| Componentes (fixture)               | precondición afirmada; 8/4/9/6 con el builder de `engine_layers`                                                                                                                                                                                                                                                                  | ídem                                                                      | quitar `inventory` de la fixture                                                                                                               |
| C3 exenta                           | `set(utility.checks) == F7(SCORE_HELP) − {C3}`                                                                                                                                                                                                                                                                                    | `test_investment_sector_calibration.py:286-305` (extendido)               | quitar C3 de `SCORE_HELP`                                                                                                                      |
| Calidad por campo                   | `what` 40–320 · `reading` 10–200 · `why` 40–320 y solape < 60 % · sin umbral (regex ampliada con signo y «del corte»)                                                                                                                                                                                                             | contrato                                                                  | «del corte −2,22» en un `reading` — hoy pasa                                                                                                   |
| Huella intacta                      | ejecutado tras A.1, A.2, A.3                                                                                                                                                                                                                                                                                                      | ídem                                                                      | — (debe NO moverse)                                                                                                                            |
| Pureza `presentation/`              | gate PROPIO: lista de directorios con `assert modulos` por directorio; import pass (IO + `random`, `time`, `os`, `uuid`, `secrets` — **no** `datetime`, que `types.py` importa) **más una pasada sobre `ast.Call`/`ast.Attribute`** que prohíbe `now/utcnow/today/time/perf_counter`; ningún `engine/*.py` importa `presentation` | `test_investment_engine.py`                                               | `datetime.now()` en `narrative.py` **y** `import random` — el gate actual sólo filtra nombres de import; la sonda del borrador daba verde      |
| Rehidratación                       | `"0.600000"` → `Decimal("0.6")`; `test_investment_analysis.py:322-336` importa el helper                                                                                                                                                                                                                                          | `test_investment_presentation.py`                                         | comparar como `str`                                                                                                                            |
| Distancia                           | itera TODAS las specs del catálogo y de los 12 perfiles; S7 bajo 1 → `next_cut_missing`; Q5 → `next_band='stressed'`; M-Score `abs/                                                                                                                                                                                               | cut                                                                       | `; `score`→`rel=null`; toda señal de pregunta con banda tiene distancia                                                                        | ídem | invertir signo en `lower_better` / usar `cut` sin `abs()` |
| Orden total                         | B4 roja antes que D2 2,1×; corte 0 vs gradiente; empate EXACTO por clave; nunca `None < número`                                                                                                                                                                                                                                   | ídem                                                                      | poner el centinela a 2 / `rel or 0`                                                                                                            |
| Origen persistido (M)               | eléctrica → `sector`; financiera en INDUSTRIALS → `financial`; fila alterada → `table`; run 1.7.0 no se deriva                                                                                                                                                                                                                    | `test_investment_sector_calibration.py` · `test_investment_thresholds.py` | cambiar un corte del fixture con `origin` presente                                                                                             |
| Stress en financieras (M)           | banco con escenario fallido → señal `unchecked`, ninguna roja                                                                                                                                                                                                                                                                     | `test_investment_engine_synthesis.py`                                     | quitar la guarda                                                                                                                               |
| Origen derivado (< 1.7.0)           | `sector` con un corte distinto; `"0.600000"` vs `0.6` → `generic`; `earlier_calibration`; `applies=False` antes de indexar                                                                                                                                                                                                        | `test_investment_presentation.py`                                         | comparar sólo `low_ok`                                                                                                                         |
| Perfil                              | `INDUSTRIALS + is_financial` → `financials`                                                                                                                                                                                                                                                                                       | `test_investment_sector_calibration.py`                                   | quitar el `or`                                                                                                                                 |
| Evidencia Py == TS                  | fixture compartido: recuento, cuatro estados, `not-recorded` OMITE claves, ningún `null` JSON, `audited` ausente + `evaluated_count>0` → `evaluated`                                                                                                                                                                              | `pytest` + `vitest`                                                       | cambiar la regla en un lado / `.get()` en la réplica                                                                                           |
| Formato Py == TS                    | `metric-format.json`: 8 unidades × signo × `null`                                                                                                                                                                                                                                                                                 | `pytest` + `vitest`                                                       | decimales de `pp` en Python                                                                                                                    |
| Goldens narrativa                   | frase exacta por celda; MCD 1.0.0 lleva su rojo; JNJ 1.3.0 sin «limpias»; portante `approximation` lleva `*`                                                                                                                                                                                                                      | `test_investment_narrative.py`                                            | una palabra de una plantilla                                                                                                                   |
| Bump narrativo                      | sha256 del TEXTO de las plantillas ↔ `NARRATIVE_VERSION`                                                                                                                                                                                                                                                                          | ídem                                                                      | cambiar plantilla sin bump                                                                                                                     |
| Prosa en plantillas                 | sin dígitos tras quitar `{…}`                                                                                                                                                                                                                                                                                                     | ídem                                                                      | «−2,22» en una plantilla                                                                                                                       |
| `next_checks`                       | financiera con stress en rojo → no aparece; temporal no auditada → prefijada; `not-recorded` → sin «nada que vigilar»                                                                                                                                                                                                             | ídem                                                                      | quitar la exclusión                                                                                                                            |
| `locateMetric`                      | todo `tab` ∈ `REPORT_TABS`; todo `sub` es sección real; `fcf_trend`/`stress` resuelven; `R4` → familia                                                                                                                                                                                                                            | `investment-report-sections.test.ts`                                      | renombrar `'evolucion'` en el registro / quitar el caso `fcf_trend` (listas intactas; backend en verde)                                        |
| Cross-link web                      | `hrefFor` invocado y fila `<a href>`; destino con `aria-current`; `metric` se borra al cambiar de pestaña y al expirar                                                                                                                                                                                                            | `tab-verdict.test.tsx` · `year-matrix.test.tsx` · test de `setParam`      | quitar `metric: null`                                                                                                                          |
| Sparkline                           | `null` < 3; huecos dichos; `ariaLabel` por unidad; `colSpan === years.length + 2` con spark y `+ 1` sin                                                                                                                                                                                                                           | `investment-sparkline.test.ts` · `year-matrix.test.tsx`                   | quitar el guard / dejar un `colSpan` fijo                                                                                                      |
| Marcas                              | escaneo de los 4 emisores sin literales fuera de `MARK` (`files.length === 4`); `marksLegend` en las 5 pestañas web y 5 móvil                                                                                                                                                                                                     | `packages/ui` · web · móvil                                               | `marks.push('§')` / quitar `marksLegend` de UNA matriz                                                                                         |
| Guía                                | toda etiqueta citada existe en `EVIDENCE_LABEL`/`bandLabel`                                                                                                                                                                                                                                                                       | `investment-report-guide.test.ts`                                         | renombrar «Sin evidencia»                                                                                                                      |
| Diff                                | filing nuevo → `company_changes`; bump → `method_changes`                                                                                                                                                                                                                                                                         | `test_investment_diff.py`                                                 | ignorar `thresholds_version`                                                                                                                   |
| Selector de runs                    | rerun borra `?run=`; con `?run=<viejo>` se pinta el viejo; móvil `onSelect` resetea                                                                                                                                                                                                                                               | web + móvil                                                               | quitar el `setParam` del `onSuccess`                                                                                                           |
| Paridad móvil                       | run **CON** `report` → la frase exacta aparece; run **SIN** la clave (omitida) → fallback; desglose, checklist, stress, alcance, confianza                                                                                                                                                                                        | `report-tabs.test.tsx`                                                    | — (el fixture va casteado con `as unknown as AnalysisRun`: un `report` omitido pasaría sin pintar nada; por eso el caso positivo afirma texto) |
| Regresión                           | 9 reglas + suites FE y BE completas                                                                                                                                                                                                                                                                                               | existentes                                                                | —                                                                                                                                              |

Regla para todos ([PHASE-47.E]): **la sonda se afirma antes de correr**, y el
test que cae tiene que ser **el que cubre la línea tocada**.

---

## 6. Orden, paradas y por qué

```
Parada 0 ─ desenredar el árbol (receta abajo) · corregir HANDOFF:10
   │
   A ── capa de significado ──── Parada A (8 fichas + 2 banderas + M-Score) ── resto
   │
   M ── motor 1.7.0: `origin` persistido + stress de financieras     (C y B lo leen)
   │
   C ── rehidratación · distancia · orden · origen · cross-links     (B la necesita)
   │
   B ── narrativa ──────────────── Parada B (plantillas con ejemplo real) ── goldens
   │
   D ── sparklines + desglose de scores (web y móvil)               (paralelizable con B)
   │
   E ── guía · marcas · glosario · paridad móvil (8 piezas) · copy ── Parada (c)
   │
   F ── comparador + historial de runs (+ `run.reset()` en móvil)
   │
   G ── print · QA de textos · knip · phase doc · README · HANDOFF
```

**Receta de la Parada 0** (medida contra `git status` del 2026-08-26):

1. **Commit 1 — 44.23 glosario.** Código disjunto: los ficheros de la tabla de
   §0.1 más `test_investment_engine_contract.py`, los dos `year-matrix.test.tsx`,
   `investment-matrix.ts`, `investment-metric-rows.ts`,
   `investment-statement-rows.ts`, `investment.ts`, `schemas.py` ×2,
   `canonical.py`, `metrics.py`, `tab-valuation.tsx`. Docs: el hunk del README;
   `git add -p` con `e` en `api/endpoints.md` y `HANDOFF.md`, porque comparten
   hunk con las otras dos entregas (`lessons.md` es sólo de 47.H).
2. **Commit 2 — 47.E4 + 47.H-2ª juntas** (comparten siete ficheros:
   `analytics`/`dashboard` schemas y servicios, `analytics.ts`, `dashboard.ts`,
   `ui/index.ts`, `category-donut.tsx`): no se prometen tres commits.
3. Decidir si los **reformateos de Prettier/EOL** de once ficheros de
   `packages/types` van en el commit 1 o se revierten con `git checkout --`.
4. Corregir `HANDOFF.md:10`.
5. Dec.A está tomada (44.24): el glosario NO se renombra; nada que hacer aquí.

- **M antes que C y B**: la presentación lee `origin` en vez de inferirlo, y
  los goldens de la narrativa se escriben contra el motor definitivo — si M
  fuera después, habría que reescribir los goldens de las financieras.
- **C antes que B**: la narrativa ordena por severidad y cita distancias.
- **D en paralelo con B**: no comparten ficheros salvo `metric-rows.ts` (D) vs
  `presentation/` (B).
- **F al final**: la superficie nueva más grande; el historial necesita runs
  que ya lleven `report.*`.
- **Cada entrega = un commit en `main`** con la suite verde (el usuario publica
  por push directo), y **la phase doc se escribe con la entrega**.

Tamaño relativo: A = redacción cara / código pequeño · C = medio (el test de
distancia contra el catálogo entero es el más largo) · B = medio-grande · D =
medio · E = muchos pequeños + ocho piezas de paridad + dos inventarios de copy ·
F = grande · G = pequeño.

---

## 7. Riesgos concretos y su guardarraíl

| Riesgo                                                                                 | Guardarraíl                                                                     |
| -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | --- | ---------------------------------------- |
| Un `@dataclass` o `Literal` en cualquiera de los tres módulos de ayuda mueve la huella | Regla única §2.A.0; gate ejecutado tras A.1, A.2 y A.3                          |
| `key="DSRI"` como kwarg cuenta como bandera emitida                                    | Dicts con la clave como clave                                                   |
| `presentation/` acaba importado por el engine                                          | Gate: ningún `engine/*.py` importa `presentation`                               |
| Comparar `thresholds_used` como texto (escala 6) etiqueta TODO como sectorial          | `rehydrate.py`; fixture de un run real                                          |
| Recalibración genérica posterior se lee como «sectorial» en runs viejos                | `earlier_calibration` en la derivación; los runs ≥ 1.7.0 traen `origin`         |
| El default `origin="generic"` esconde un corte de tabla                                | `load_thresholds` compara numéricamente y marca `table`; test con fila alterada |
| Etiqueta de perfil desde `security.sector` miente en financieras y socimis             | `threshold_profile_key` en el engine; lo emite el servidor                      |
| La narrativa esconde rojos de runs viejos tras «motor anterior»                        | Plantilla `not-recorded` con etiquetas; golden de MCD                           |
| «Comprobadas y limpias» en runs sin `outcome` (JNJ 1.3.0)                              | `outcomes_recorded` con la MISMA prueba que `evidenceBreakdown`                 |
| `rel` negativo con cortes negativos invierte el orden; `rel` sin sentido en `score`    | `abs/                                                                           | cut | `; `rel=null`en`score`; test con M-Score |
| Sonda de pureza que no entra                                                           | Pasada por `ast.Call`; sonda doble                                              |
| Sonda de `locateMetric` que tumba otro test                                            | Registro único; invariantes sobre `tab`/`sub`/derivadas                         |
| Gate de marcas tautológico                                                             | Escaneo de literales en 4 ficheros con guard de recuento                        |
| Gate de componentes verde por una rama no ejercitada                                   | Escaneo estático por función + fixture con precondición afirmada                |
| Fixture bilingüe con `null` donde debe faltar la clave                                 | `null` fuera de dominio, afirmado en las dos suites                             |
| `metric` pegajoso en la URL                                                            | `metric: null` en tab/sub/expiración + test                                     |
| Hooks de router dentro de `SignalTable` producen `"null?tab=…"` sin fallo              | `hrefFor` inyectado desde `page.tsx`                                            |
| Selector de runs que nunca puede enseñar un run viejo                                  | Precedencia `selected ? … : …` + borrado en el rerun                            |
| Rerun de A mostrado como informe de B en móvil (bug vivo)                              | `run.reset()` en `onSelect` (F.3)                                               |
| Bump 1.6.1 marca caducado todo run guardado por una frase                              | Sin bump (Dec.F)                                                                |
| Dos formateadores / dos tri-estados divergen                                           | Fixtures compartidos en `packages/ui/src/__fixtures__/`                         |
| Columna de tendencia desalinea filas sin serie                                         | Tri-estado de `spark` + filler vacío + test de `colSpan` en ambos casos         |
| `report-tabs.tsx` (779 líneas) inmantenible                                            | Partir por pestaña en D                                                         |
| Subagentes ejecutan `pytest` durante la suite                                          | Prohibición explícita en cada prompt ([PHASE-44.10])                            |
| Agente redactor muerto = bloque vacío que parece limpio                                | Cobertura por bloque; vacío es rojo                                             |

---

## 8. Decisiones tomadas por el usuario (2026-08-27)

(Se numeran Dec.A–G y no D1–D6: «D5» ya nombra una decisión del
`DESIGN-v2-investment-module.md` y el alcance P5 la cita.)

| #     | Decisión                          | Elegido                                   | Efecto en el plan                                                              |
| ----- | --------------------------------- | ----------------------------------------- | ------------------------------------------------------------------------------ |
| Dec.A | Numeración                        | **44.24**                                 | Los dos documentos renombrados; el glosario sigue siendo 44.23                 |
| Dec.B | Procedencia del corte             | **Persistir `origin` en `ThresholdSpec`** | Entrega M (motor 1.7.0) antes de C; la derivación queda sólo para runs < 1.7.0 |
| Dec.C | Dónde vive el texto               | **Python**                                | `presentation/narrative.py` + `format.py` atado por fixture                    |
| Dec.D | `next_checks` sin ámbar ni rojo   | **Pintar con recuento**                   | Prohibido si hay preguntas `not-recorded`/`not-audited`                        |
| Dec.E | Sparklines en Estados             | **Fuera**                                 | `spark` ausente en las filas de partidas (tri-estado)                          |
| Dec.F | Bump por la pasada de copy        | **No**                                    | Nota bajo 1.6.0 en el historial; ningún run marcado caducado por una frase     |
| Dec.G | Stress de financieras en el motor | **Sí** (recomendación)                    | Va en M, con Dec.B: un solo bump                                               |

---

## 9. Fuera de alcance

Sin cambios respecto al documento: score global · benchmarks vivos ·
recomendaciones · narrativa por LLM · pestaña Valoración · comparación entre
empresas. Añadido: **persistir la capa de presentación** (§1.1), **sparklines en
Estados** (Dec.E), y **los tres charts de 44.22 siguen sólo en web** (backlog)
— el dumbbell es SVG a mano y podría entrar en D.3 con el mismo `<Svg>` si el
usuario lo pide.

---

## 10. Revisión adversarial de este plan (registro)

Método: cinco lentes independientes (contrato del motor · reglas de honestidad
y runs viejos · capa compartida y móvil · ceguera de gates · premisas caducadas
y alcance), sólo lectura, con la prohibición explícita de ejecutar tests, y un
escéptico independiente por hallazgo que intenta refutarlo contra el código.

| Ronda          | Agentes                                                                                                                          | Hallazgos                                  | Resultado                                                                                                                                                      |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1 (2026-08-26) | **5/5** lentes vivas (22–48 ficheros leídos cada una) · 10/10 verificadores                                                      | 41 brutos (9 altos · 20 medios · 12 bajos) | 10 verificados: **7 confirmados · 3 parciales · 0 refutados**; el tope del harness dejó 19 altos/medios sin verificar                                          |
| 2 (2026-08-27) | primer intento **0/16 ejecutados** (límite de sesión — lo dijo el bloque de fallos, no un resultado vacío) · reintento **16/16** | 16 (3 duplicados excluidos)                | **6 confirmados · 10 parciales · 0 refutados**. Los «parciales» sostienen el núcleo y corrigen el mecanismo o la cita; todas las correcciones están integradas |

De los 26 altos/medios, ninguno se refutó. Las correcciones que los verificadores
hicieron a los propios hallazgos también se aplicaron (Next 15 devuelve `null`
en vez de lanzar; la precedencia del selector de runs que el hallazgo proponía
era defectuosa; «tres commits» no es alcanzable; el hero móvil sí pinta
`engine_version`). Los 12 bajos se aplicaron cuando eran de precisión. Dos
hallazgos fuera del alcance del documento quedan dichos aquí para el backlog: el
leak de `run.data` entre valores en móvil (§0.3, lo arregla F.3) y que la
contradicción stress-rojo / pregunta-no-auditable ya existe hoy dentro de la
`SignalTable` (Dec.G).
