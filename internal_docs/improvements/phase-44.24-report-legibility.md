# PHASE-44.24 — Capa de legibilidad del informe de análisis

> **Renumerada 44.23 → 44.24 el 2026-08-27** (decisión del usuario): el número
> 44.23 ya nombra al glosario («Qué es cada fila del informe»), construido el
> mismo día que se escribió este documento y del que esta fase depende. El plan
> de implementación —que manda sobre este documento en lo que corrige— está en
> [`phase-44.24-report-legibility-implementation-plan.md`](phase-44.24-report-legibility-implementation-plan.md).

**Estado**: 📋 planificada — alcance completo (criterio del usuario: coste no
es restricción; sí lo es la coherencia con la filosofía del motor).
**Origen**: revisión de comprensibilidad (2026-08-23). Diagnóstico: el
informe es **auditable pero no legible** — demuestra todo y explica poco.
Tres huecos verificados contra código: (1) `MetricDefinition` no tiene campo
de significado; (2) el semáforo es binario por señal — la **distancia al
corte** no se muestra; (3) nivel sin **dirección** — las series existen en el
run pero no se ven en las filas.
**Depende de**: 44.9 (contrato del informe + 6 reglas de honestidad en
`metric-rows.ts`), 44.20 (secciones compartidas web/móvil), 44.21
(calibración sectorial viva, `thresholds_used`), 44.22 (infraestructura de
charts).

## Principios (no negociables)

- **P1**: toda pieza nueva respeta y extiende las **seis reglas de
  honestidad** existentes; ninguna las puentea.
- **P2**: **una sola fuente para cada texto** — significado de métricas en el
  catálogo del engine; banderas en `flag_catalog`; scores en un
  `score_help` hermano. La UI jamás hardcodea definiciones.
- **P3**: **determinismo**: las frases del veredicto se generan por plantilla
  parametrizada, server-side, con **goldens de texto**. Jamás LLM, jamás
  aleatoriedad, jamás texto que no pueda reproducirse de un run.
- **P4**: **paridad móvil por construcción**: todo aterriza en las secciones
  compartidas de 44.20; nada web-only salvo lo marcado (print).
- **P5**: siguen prohibidos: score global único / media ponderada opaca
  (contra D5), benchmarks de mercado vivos dentro del informe (rompen
  determinismo), y cualquier lenguaje de recomendación de compra.

---

## 44.23.A — Backend: la capa de significado (la base de todo)

### Catálogo de métricas

`MetricDefinition` gana tres campos de texto plano (español, tono del
proyecto):

```python
what: str      # qué mide, 1 frase.  "Cuántos años de caja libre costaría
               # devolver la deuda neta."
why: str       # por qué importa (sesgo tesis-dividendos), 1 frase.
               # "Deuda que compite con tu dividendo por la misma caja."
reading: str   # cómo leerla. "Menos es mejor; compárala con su banda
               # sectorial y con su propia serie."
```

### Banderas y scores

- `flag_catalog.py` (18 banderas): mismos tres campos + `how_to_verify`
  ("dónde mirarías en los estados para confirmarla") — las banderas son la
  escuela de lectura forense.
- `score_help.py` (nuevo, hermano del flag_catalog): ficha por score
  (M, Z'', F, Sloan, C-Score, FZ si entra) con `what/why/reading` **y una
  entrada por componente** (las 8 variables de M, los 4 X de Z'', los 9
  tests de F, los 6 checks de C) — una frase cada una.

### Contrato y gates

- El endpoint de catálogo existente (44.9 §1) transporta los campos nuevos;
  bump del schema de API (no de `engine_version`: es metadato, no cálculo).
- **Gate de contenido en CI**: test que falla si cualquier métrica, bandera,
  score o componente tiene un campo de significado vacío. La capa no puede
  degradarse por olvido en métricas futuras.
- **Parada A (contenido)**: ~40 fichas de métrica + 18 banderas + ~30
  componentes de score son la parte cara. Redacción en dos tandas: primera
  tanda de 8 fichas → **revisión de tono por el usuario** (es su informe y
  su voz) → resto con el patrón aprobado. Los textos congelan en goldens.

## 44.23.B — Frases-veredicto deterministas (server-side)

Módulo **puro** `analysis/presentation/narrative.py` (misma disciplina AST
que el engine; versionado propio `NARRATIVE_VERSION` incluido en la
respuesta):

- **Una frase por pregunta**, plantilla por (pregunta × estado) parametrizada
  con las señales portantes y sus valores:
  _"La contabilidad parece fiable: M-Score −2,61 (holgado del corte −2,22),
  accruals 2,8 %; ninguna bandera de cocina activa."_
  Estados `no_auditado`/`sin evidencia` tienen sus plantillas propias que
  dicen POR QUÉ (la honestidad también se narra).
- **"Qué miraría a continuación"**: 2-3 bullets generados de las señales
  ámbar más severas (por distancia normalizada, ver C):
  _"Payout FCF al 82 % — vigila D2 en el próximo filing."_
- Viaja en el payload del run (`verdict.narrative`), así web y móvil lo
  pintan idéntico sin duplicar lógica (P4).
- **Goldens de texto** en pytest: un fixture por (pregunta × estado) con la
  frase exacta esperada. Cambiar una plantilla = cambiar un golden,
  conscientemente.
- **Parada B**: las plantillas iniciales (≈14: 4 preguntas × 3 estados + 2
  especiales) pasan por el usuario antes de congelar goldens.

## 44.23.C — Señales con gradiente y procedencia

Sobre `signal-table` (compartida):

1. **Distancia al corte**: "a 0,3× del verde" / "2,1× dentro del rojo",
   calculada del valor y el corte **efectivo** (`thresholds_used`, ya
   priorizado por `metric-index`). Formato por unidad reutilizando
   `metric-format`.
2. **Orden por severidad**: las señales de cada pregunta se ordenan por
   distancia normalizada (peor primero). El ojo cae donde duele.
3. **Procedencia del corte**: label junto al corte — "banda UTILITIES" /
   "banda genérica" / "sin calibrar (IFRS)" — del propio `thresholds_used`.
   Dos empresas con cortes distintos dejan de parecer un bug.
4. **Cross-links**: cada señal del veredicto enlaza a su fila en la pestaña
   correspondiente (abre pestaña + scroll + highlight temporal). El camino
   veredicto→evidencia pasa de "búscalo" a "un click".

## 44.23.D — La dirección: series en las filas

1. **Sparkline por fila** (5 puntos, serie del run) en Ratios, desglose
   forense y Dividendo — con la infraestructura de 44.22. Celda vacía si
   <3 años (regla 6: hueco visible, no omitido).
2. **Tendencia de scores**: en cada score, delta vs año anterior con flecha
   y la mini-serie (Z'' 3,1 → 2,8 → 2,6 cuenta otra historia que "2,6
   verde").
3. **Accesibilidad**: cada sparkline con `aria-label` textual generado
   ("serie 5 años: 3,1; 2,9; 2,8; 2,7; 2,6 — descendente"). El label lo
   genera la misma utilidad para web y móvil.

## 44.23.E — Lectura guiada y jerarquía

1. **Veredicto como pestaña de aterrizaje** (hoy el orden es el del
   cuaderno, Estados primero). El informe abre por la respuesta.
2. **"Cómo leer este informe"** plegable en el veredicto: las 4 preguntas,
   el orden recomendado (Veredicto → pregunta no-verde → su pestaña), y qué
   significa cada estado (verde/ámbar/rojo/gris/sin-evidencia).
3. **Leyenda universal de marcas** (`*` aproximación, `·` imputado, `†`
   derivado, `≈` estimado, gris = no aplica/sin banda): accesible a un click
   desde LAS CUATRO pestañas de métricas — hoy exige memoria. Test que
   afirma su presencia en las cuatro.
4. **Glosario**: sheet agregada de todas las fichas (A) navegable por capa,
   alcanzable desde cualquier "?" y desde la lectura guiada. Sin contenido
   propio: renderiza el catálogo (P2).
5. **Hero ampliado**: al chip de perfil se suman los **4 puntos de las
   preguntas** (mini-semáforo), el chip de dividendo (`dividend_verdict`)
   cuando aplique, y confianza+staleness compactos. Un vistazo, en
   cualquier pestaña.
6. **Confianza explicada**: la fórmula con los números reales del run
   ("completitud 9/10 partidas núcleo × factor frescura 1,0 (cierre hace
   3 meses) = 0,90") y qué la subiría.
7. **Pasada de copy sobre estados degradados**: `degraded-panel` y todos los
   `not_computable/not_applicable` con razones en español de negocio, no de
   motor. Tabla de reescritura en el doc de la sub-fase; las razones son
   parte del contrato del run, así que la reescritura vive donde nacen
   (engine), no en la UI.

## 44.23.F — Comparador de runs (la misma empresa en el tiempo)

El flujo real del usuario es recurrente: re-analizar la misma empresa con
cada filing. Hoy cada run es una foto; el diff es mental.

- Entrada: historial de runs de la security → "comparar con el anterior".
- **Diff estructurado** (server-side, determinista, sobre los dos payloads
  persistidos): señales que cambiaron de banda (con ambos valores),
  banderas nuevas/retiradas, deltas de scores, preguntas que cambiaron de
  estado, statements añadidos (filing nuevo) y **restatements detectados**.
- **Distinción de causa obligatoria**: cambio con mismo
  `engine_version`+`thresholds_version` = _cambió la empresa_; con versión
  distinta = _cambió el motor/la calibración_ — se muestran en secciones
  separadas y etiquetadas. Sin esta distinción el comparador desinforma
  (es la razón de ser del versionado de Dec.7).
- UI: vista de dos columnas + lista de cambios ordenada por severidad.
  Fixture de test: dos runs que difieren por un filing vs dos que difieren
  por bump de thresholds — el diff los separa correctamente.

## 44.23.G — Dictamen portable + cierre

1. **Vista imprimible del veredicto** (print CSS, web-only marcado):
   checklist + frases narrativas + confianza + alcance declarado + hash del
   run. El "cuaderno" que se puede archivar por año.
2. QA de contenido final: relectura completa de fichas y plantillas con el
   usuario; congelación de goldens.
3. `knip` + barrido de cualquier componente que E deje huérfano.

---

## Tests (además de los citados por sub-fase)

| Qué                    | Afirma                                                                                |
| ---------------------- | ------------------------------------------------------------------------------------- |
| Gate de contenido (CI) | Ninguna métrica/bandera/score/componente sin ficha                                    |
| Goldens narrativa      | Texto exacto por (pregunta × estado); `NARRATIVE_VERSION` bump obligatorio si cambian |
| Distancia al corte     | Cálculo por unidad correcto en las 8 unidades de `metric-format`                      |
| Orden por severidad    | Determinista; empates estables por clave                                              |
| Leyenda                | Presente en las 4 pestañas de métricas                                                |
| Sparkline a11y         | `aria-label` textual correcto, incluida serie incompleta                              |
| Comparador             | Fixture filing-nuevo vs fixture bump-thresholds → secciones separadas                 |
| Paridad                | Las secciones compartidas renderizan en móvil (suite 44.20)                           |
| Regresión              | Las 6 reglas de honestidad siguen afirmadas por los tests existentes; 133+ web verdes |

## Puntos de parada

(a) **Tono del contenido** — tras las primeras 8 fichas, revisión del
usuario antes del resto. (b) **Plantillas narrativas** — revisión del
usuario antes de congelar goldens. (c) Cualquier razón de motor que no
tenga traducción de negocio clara en E.7 → preguntar, no inventar.

## Fuera de alcance

Score global único · benchmarks de mercado vivos · recomendaciones de
compra/venta · narrativa por LLM · cambios en la pestaña Valoración
(44.12, camino propio) · comparación entre empresas distintas (el
comparador es misma-security; el cross-company exigiría normalizaciones
que hoy serían falsa precisión).
