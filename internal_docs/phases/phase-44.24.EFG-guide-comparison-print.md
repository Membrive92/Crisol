# PHASE-44.24.E/F/G — La guía, el comparador y el dictamen imprimible

**Estado**: 🚧 pendiente prueba manual
**Rama**: `main` (push directo)
**Fecha**: 2026-08-27

Tres entregas que cierran PHASE-44.24. Se documentan juntas porque comparten el
mismo movimiento: **lo que la pantalla dice deja de estar escrito en la pantalla**.

---

## E — Lectura guiada y jerarquía

### E.3 · Las marcas, declaradas una vez

Las marcas de una celda estaban definidas en **tres** sitios
(`PROVENANCE_MARK`/`PROVENANCE_TITLE` en `investment-metric-rows.ts`,
`provenanceMark()`/`provenanceTitle()` en `investment-statement-rows.ts`, y
literales sueltos), y **sus títulos ya divergían**: el mismo `·` era «el filing
no publica el concepto» en un sitio y «no etiqueta el concepto» en el otro.
Publicar y etiquetar no son lo mismo, y el usuario no tenía forma de saber cuál
estaba leyendo.

Peor que la divergencia: **sólo dos de las cinco pestañas de matriz pintaban
leyenda**. En Evolución, Forense y Dividendo un `†` o un `≈` salían sin
explicación — una marca sin leyenda es ruido tipográfico.

- `packages/ui/src/investment-marks.ts` — `MARK` con glifo **y** título por
  entrada. `MATRIX_LEGEND` se DERIVA de ahí, así que una marca nueva aparece
  explicada en las cinco pestañas sin tocarlas.
- `TEXT_LEGEND` va **aparte**: un `—` es lo que se pinta EN LUGAR del número, no
  una anotación sobre un valor que existe. `REPORT_LEGEND` las junta para pintar.
- `YearMatrix` (web y móvil) gana `marksLegend`, separado de `legend` (la prosa
  propia de cada pestaña). En móvil eso obliga a que la leyenda deje de ser una
  sola cadena.

**El gate**. «La leyenda contiene todas las marcas» se cumple **por
construcción** y no prueba nada. El que vale escanea el fuente de los **cuatro**
emisores buscando cualquier literal de un solo glifo. La primera versión anclaba
el patrón a `push|return|mark:` y una sonda lo tumbó: `provenance === 'derived' ?
'†' : …` lo pasaba entero. Ahora el patrón es el glifo, venga como venga —
las **cuatro** sondas muerden, incluidas las dos de otro paquete.

### E.2/E.4 · «Cómo leer este informe»

`packages/ui/src/investment-report-guide.ts`: seis secciones (colores, ausencias,
marcas, evidencia, procedencia del corte, orden de lectura). **Los estados no se
escriben ahí**: se importan de donde se pintan (`bandLabel`, `EVIDENCE_LABEL`, el
registro de marcas), de modo que la guía no puede describir un vocabulario que la
pantalla ya no usa — que es exactamente cómo caducó la leyenda del forense en
PHASE-44.17.

Web: página `/investments/analysis/guide`. Móvil: hoja modal desde el hero, para
no perder la pestaña en la que estabas.

### E.5/E.6 · Paridad móvil

`SAFETY` estaba **duplicada** en `analysis-hero.tsx` y `tab-verdict.tsx`, y las
cinco reglas del perfil Conservador escritas a mano en el segundo. Copiarlas a
móvil habría hecho **cuatro** copias de lo que decide `_safety_profile` en el
motor: en cuanto el motor añada una condición, las cuatro mienten a la vez.

A `packages/ui`: `SAFETY`, `DIVIDEND`, `safetyRules()` (el checklist evaluado
contra `blocking_reasons`), `CORE_ITEMS` y `coreItemCoverage()`.

Móvil gana, todo a paridad: los cuatro `BandDot` con `questionEvidence`, el
titular del servidor, el veredicto del dividendo, `thresholds_version`, la fecha,
el aviso de motor anterior, el checklist del perfil, la frase por pregunta,
«qué miraría a continuación», los escenarios de stress con
`breakeven_fcf_drop` y `not_computable_reason`, la tarjeta de alcance, la sección
de confianza y la cobertura de partidas núcleo.

### E.7 · Pasada de copy

Las razones del motor acaban **impresas** en el informe. Interpolar la clave
canónica —«falta la partida `'ltd_current_portion'`»— le pide al usuario que
aprenda un vocabulario interno para entender por qué su empresa no tiene un
número.

`item_label()` en `engine/types.py` traduce en el origen desde
`CANONICAL_ITEM_DEFINITIONS` (la misma fuente que las 49 claves, así que
renombrar una partida no deja la frase mintiendo). Cinco puntos corregidos en
`types.py`, `conventions.py` y `evolution.py`.

**Sin bump** (Dec.F): la política de `version.py` es «fórmula o métrica nueva»,
la huella no cambia, y `isRunOutdated` compara también el PATCH — un 1.6.1
pondría el aviso «motor anterior» en **todos** los runs guardados por una frase.

Gate: `tests/test_investment_engine_copy.py` recorre las **49** partidas reales
—no un ejemplo— y comprueba que ninguna razón por defecto deja escapar una clave.
Más la sonda del propio detector.

**Y tres tests que afirmaban la jerga vieja.** `test_investment_engine.py` exigía
`"current_liabilities" in metric.reason` y `test_investment_engine_synthesis.py`
`"falta la partida '"cogs"'"` dos veces. Los tres pasaron a afirmar el
invariante nuevo —la etiqueta humana SÍ, la clave del motor NO—, que es más
fuerte que el anterior. No los cazó la pasada que creí haber ejecutado: el
`cd backend` de ese comando falló, el `&&` cortó y el `tail` me devolvió el
resultado de un log anterior. Está en `lessons.md`.

---

## F — Comparador de runs

La tabla guarda un `AnalysisRun` por ejecución y `useAnalysisRuns` existía desde
44.7 **sin ningún consumidor**: no había forma de abrir un análisis que no fuera
el último, ni de ver qué se había movido.

**La distinción que gobierna el módulo**: un cambio puede venir de la EMPRESA
(publicó otro ejercicio, sus números se movieron) o del MÉTODO (subió el motor,
se recalibraron los umbrales). Presentarlos juntos sería **peor que no
comparar**: leer «el Z''-Score pasó de verde a ámbar» como una degradación del
negocio cuando lo que cambió fue el corte es la conclusión contraria.

Por eso `comparable` es una **precondición y no una etiqueta**: si el motor o los
umbrales difieren, no se emite ni un solo cambio de empresa.

- `presentation/diff.py` (PURO) — `diff_runs(base, target, restatements)`.
- `GET /investment/analysis/{id}/runs/compare?base=&target=` — sin ids, los dos
  últimos. `base` es SIEMPRE el más antiguo, elija el usuario el orden que elija:
  un diff al revés diría que un score «mejoró» cuando empeoró.
- `AnalysisRunSummary.thresholds_version` (una línea) para etiquetar
  «comparable» en el selector sin pedir los runs enteros. **Opcional en TS**:
  un backend anterior no lo manda, y `campo !== undefined` sobre una clave
  ausente es cómo se pinta una marca en todas las filas (lección PHASE-47.E).
- `diffRows()` en `packages/ui` — lo que **empeora** va primero, que es lo que
  hace mirar esta pantalla.
- Web: sub-pestaña «Qué ha cambiado» bajo Veredicto, `?run=` y `?compare=` en la
  URL. Móvil: bloque plegable bajo el hero.

**La precedencia del run activo NO es `run.data ?? selectedRun.data ?? …`**:
`useMutation.data` persiste mientras la página esté montada, así que con ese
orden el selector no podría enseñar nunca un run viejo tras un rerun. Que «un
rerun recién hecho gane» se consigue **borrando la selección** en el handler.

De paso, un **leak preexistente** de móvil: `run.reset()` en `onSelect` del
buscador. Sin él, el análisis que acabas de lanzar sobre MCD se presenta como el
informe de la empresa que acabas de elegir.

**Nueve sondas, las nueve muerden.** Dos no mordían al principio y las dos eran
defectos míos:

1. `compare()` tenía **dos guardas solapadas** para «falta un extremo», así que
   romper una la tapaba la otra: el test no podía distinguir cuál protegía. Una
   sola guarda.
2. El test del ejercicio del dictamen llegaba al verde **por otro camino**: los
   metrics del fixture estaban en orden ascendente, así que sin el filtro por año
   el diccionario se quedaba igualmente con el correcto. Invertido el orden.

---

## G — Dictamen imprimible

No había **ninguna** regla `@media print` en la app: imprimir sacaba la barra
lateral, las pestañas y los botones, con fondo oscuro si el tema lo estaba.

`?print=1` fuerza la pestaña de Veredicto y añade una cabecera con `run.id`, las
**tres** versiones, la fecha y el alcance. Un papel sin eso no es auditable: el
mismo valor con otra calibración da otros colores.

El cromo se esconde con `data-print="hide"` que declara el propio componente —
nada depende de la estructura del layout, que cambiaría sin avisar.

---


---

## La revisión adversarial (y por qué casi no cuenta)

Se lanzó un workflow de seis lentes con dos escépticos ortogonales por hallazgo
y un crítico de completitud: **19 agentes, 18 murieron por límite de sesión**.
Devolvió `confirmados: 0`, que es carácter por carácter lo que devuelve una
revisión limpia — y los seis hallazgos que sí salieron venían con el motivo
VACÍO, porque nadie llegó a refutarlos. Es la lección [PHASE-44.14] otra vez, y
esta vez con la agravante de que sólo una lente de las seis llegó a ejecutarse.

Los seis se verificaron **a mano, leyendo el código**. Los seis eran reales:

| # | Qué | Efecto |
|---|---|---|
| 1 | `noRunYet` no miraba el estado del run SELECCIONADO | Con `?run=` en la URL, la pantalla decía «todavía no se ha ejecutado ningún análisis» —falso— mientras esa query cargaba, y **desmontaba el selector con el que acababas de pulsar**. Con un id que no existe, se quedaba ahí para siempre |
| 2 | `href="?print=1"` | Una referencia relativa de sólo query SUSTITUYE la query entera (RFC 3986 §5.3): el dictamen impreso era el del análisis más RECIENTE, no el que estabas mirando. En un papel que se archiva |
| 3 | La barra de pestañas se renderizaba en modo dictamen | `data-print="hide"` sólo la esconde dentro de `@media print`. En pantalla seguía viva, y pulsarla escribía un `tab` que `printMode` descarta: la barra decía una cosa y la página enseñaba otra |
| 4 | `notEnoughRuns={comparison.isError}` | El servidor distingue CUATRO motivos de 404 con su frase escrita; la UI los colapsaba en «hace falta más de un análisis», que en tres de los cuatro es falso — y encima tapaba un 500 o la red caída |
| 5 | La guarda de «comparar consigo mismo» vivía dentro de UNA rama | Con los dos ids iguales caía en la otra rama y devolvía un diff vacío, que la pantalla anuncia como «nada se ha movido»: cierto y engañoso a la vez |
| 6 | `run.isError` sólo dentro de `hasStatements && noRunYet` | Ese bloque por definición no está en pantalla cuando ya hay informe — que es justo cuando se pulsa «Volver a analizar». Y `void rerun()` dejaba el rechazo suelto |

**Y los arreglos destaparon dos gates míos que no valían.** Al sondearlos, dos de
siete no mordían, y las dos veces por lo mismo: comprobaban PRESENCIA. El del
href miraba que la composición partiera de los params actuales — un
`delete('run')` metido en medio lo pasaba entero. El del error de re-análisis
buscaba la cadena `rerunError` en el fichero, que aparece igual en la
declaración de la prop y en su JSDoc aunque se vacíe el render.

Los dos pasaron a ser pruebas de EFECTO: `printHrefFor` se extrajo a
`apps/web/lib/report-links.ts` como función PURA con sus tests (uno afirma que
conserva `?run=`), y el hero ganó `analysis-hero.test.tsx`, que lo renderiza y
busca el texto del error. Al gate de texto le queda sólo el cableado.

Un tercer detalle del mismo tipo: el gate se cazó **a sí mismo**. El docstring
del hero cita `href="?print=1"` como ejemplo de lo que NO hay que hacer, y un
escáner que no distingue código de prosa reporta la explicación del arreglo como
si fuera el defecto. Ahora quita los comentarios antes de escanear.

**Siete sondas, las siete muerden.**

## Verificación

- BE: ruff · black · mypy 239 · **suite completa 1602 passed** (ejecutada
  DESPUÉS de los seis arreglos, no antes) · subconjunto de inversión: 727.
- FE: typecheck · lint · knip · web **271** · ui **210** · móvil **83**.
- **27 sondas entre D, E, F, G y los arreglos de la revisión; las 27 muerden.**

## Limitaciones conocidas

- El comparador **no** dibuja el dumbbell ni ningún chart: es una lista de
  cambios, y un chart de dos puntos no añadiría nada.
- La vista imprimible es **sólo web** y sólo del veredicto. Imprimir las matrices
  completas necesitaría paginación de tablas, que es otro problema.
- **La vista imprimible no tiene test automático.** Lo que hay que comprobar es
  que el cromo NO se pinta y que el fondo sale blanco, y las dos cosas viven en
  una regla `@media print` que jsdom no evalúa. Un test de PRESENCIA
  («¿existe `data-print`?») daría verde con la regla CSS borrada, que es
  exactamente la clase de guardarraíl que esta familia de fases lleva
  desmontando. Queda para la prueba manual, declarado aquí en vez de fingido.
- El selector de runs de móvil no ofrece elegir la BASE de la comparación
  (siempre el anterior): en un teléfono, dos selectores para la misma pregunta
  son más de lo que la pantalla puede sostener.
