# PHASE-44.24.C — La señal deja de ser un color: distancia, orden y procedencia

**Estado**: 🚧 pendiente prueba manual · **cross-links (C.4) pendientes**
**Rama**: `main` (push directo)
**Fecha**: 2026-08-27
**Plan**: [`improvements/phase-44.24-report-legibility-implementation-plan.md`](../improvements/phase-44.24-report-legibility-implementation-plan.md) §2.C

## Objetivo

El semáforo es binario: verde, ámbar o rojo. Pero «rojo por un pelo» y «rojo por
el triple» piden cosas distintas, y la pantalla no las distinguía. Tres cosas
nuevas por señal: **a qué distancia está de su corte**, **en qué orden hay que
leerlas** y **de dónde salió la vara**.

## Dónde vive, y por qué ahí

Paquete nuevo `analysis/presentation/`, **puro** y calculado **al leer el run**,
no al escribirlo. Tres razones, y ninguna es de estilo:

1. La tabla contiene runs de todas las versiones del motor. Calculado aquí, el
   run de McDonald's de 1.0.0 recibe su capa de lectura **hoy**, sin reejecutar
   nada. Persistido, sólo la tendrían los runs futuros.
2. Cambiar un formato no puede exigir reejecutar el motor: el run es
   reproducible por `engine_version + thresholds_version`, y una frase no forma
   parte de eso.
3. Un solo cálculo para las dos apps. El servidor manda los números; el texto lo
   compone `packages/ui`, que ya sabe formatear por unidad.

El enganche está en el **router** y no en el servicio, porque es donde ocurre la
serialización: `_with_report` envuelve las tres rutas que sirven un run entero,
así que no puede quedar una que lo devuelva sin su capa.

## Las cuatro formas del catálogo que rompen la aritmética ingenua

Todas reales; ninguna la habría encontrado una rejilla de casos escrita a mano:

| Forma | Métrica | Qué pasa |
|---|---|---|
| Banda de un solo lado | **S7** tiene `low_ok`, `high_ok`, `high_alarm` y **ningún** `low_alarm` | Por debajo sale ámbar y no puede salir rojo nunca. No hay corte siguiente: se declara en vez de fabricar uno |
| Cortes iguales | **Q5** y **T3**: `high_ok == high_alarm` | La región ámbar es VACÍA. Una etiqueta «a X del ámbar» nombraría una banda que para esa métrica no existe |
| Cortes negativos | **M-Score** (−2,22), **X-Score** (−1,04) | La relativa se calcula sobre `\|corte\|`. Con el signo, un M-Score muy dentro del rojo daría relativa NEGATIVA y el orden lo pondría como el menos grave |
| Corte cero | **T2** | No se divide |

Y una decisión propia: en las métricas de **puntuación** no se publica distancia
relativa. Los cortes del X-Score están en −1,04 y −0,25, así que la misma
distancia absoluta da relativas de 0,2 y 0,8 según con cuál se divida, sin que
ninguna informe de nada.

El test recorre las specs **reales** de tres perfiles con un valor en cada
región de cada una, en vez de una rejilla «3 direcciones × 2 lados × 8
unidades» — que suena exhaustiva y no contiene ni S7 ni Q5.

## El orden es TOTAL, y esa palabra es el trabajo

`(banda, ¿tiene gradiente?, distancia con signo, clave)`.

La decisión que el plan dejaba indefinida: **una señal roja sin gradiente va
ANTES que una con gradiente en la misma banda**. Una bandera encendida no tiene
distancia que medir; tratarla como distancia cero la colocaría «exactamente en
el corte», es decir la MENOS grave de las rojas — cuando una bandera que salta
es evidencia binaria y ya ha demostrado lo suyo.

Nunca se compara `None` con un número: en Python eso lanza y en TypeScript se
convierte en cero en silencio, que es peor. El centinela va en su propio
componente de la tupla.

## La procedencia: ocho valores, no dos

`generic` · `sector` · `financial` · `table` · `earlier_calibration` ·
`uncalibrated` · `not_applicable` · `not_recorded`.

Con los dos que tenía el borrador —genérica o sectorial— cualquier recalibración
genérica **posterior al run** se habría leído como «banda sectorial», y para una
empresa sin perfil como «perfil actual: unknown»: el falso «esto parece un bug»
que la fase existe para quitar. Desde el motor 1.7.0 (entrega M) la procedencia
**se lee del run**; los ocho valores existen para los runs anteriores, donde se
deriva y se dice que es una derivación.

Y `not_recorded` no es «pre-44.9»: un run de 1.3.0 tiene `thresholds_used` y no
tiene S7 ni S8, porque el motor de entonces no las emitía.

## Dos defectos que salieron del camino

**La rehidratación reventaba con un `applies=False` sin motivo.**
`ThresholdSpec` exige la razón —un «N/A» mudo es indistinguible de un fallo de
cálculo— y la hace cumplir lanzando. Aquí no se puede lanzar: esto lee un
documento de hace años y un campo que falte no puede tumbar la pantalla entera.
Ahora declara la ausencia, que cumple el invariante por el motivo por el que
existe.

**El gate de pureza no veía el reloj.** Miraba nombres de import, así que
`from datetime import datetime; datetime.now()` lo atravesaba entero — y
`datetime` no se puede prohibir, porque `types.py` lo usa. La mitad «sin reloj»
de la promesa dependía de la disciplina de quien escribiera el módulo. Ahora hay
una segunda pasada sobre `ast.Call`, parametrizada por directorio y con un
`assert` de que cada uno tiene módulos: un directorio renombrado pasaría el
bucle sin ejecutar una sola comprobación.

## Un test mío que pasaba por la razón equivocada

El primer test del orden en la API comprobaba que `severity_rank` fuera
`0..n−1`. **Eso es cierto por construcción de `enumerate` aunque nadie ordene
nada** — lo destapó una sonda que quitó el `sort` y dejó el test en verde.
Ahora se cruza con las bandas del veredicto persistido y se afirma que ninguna
señal va por delante de otra de banda peor. Con esa versión, la misma sonda
tumba el test.

## Verificación

- Backend: ruff · black · mypy 236 ficheros · 23 tests de la capa pura + 2 de
  API. **Diez sondas**, cada una cayendo en el test que la cubre.
- Frontend: typecheck · lint · knip · **140 tests en `@crisol/ui`** (+14) · 238
  web · 106 services · 83 móvil. Tres sondas más sobre la lectura compartida.

## Limitaciones conocidas

- **C.4 (cross-links) no entra todavía**: enlazar una señal del veredicto con su
  fila en la pestaña correspondiente, con el registro único
  `SECTION_PLACEMENT` del que se derivan `allScreenMetricKeys()` y
  `locateMetric()`. Es la pieza que queda de C.
- **Sólo web**: `SignalList` de móvil todavía no consume el `report`. Va con la
  paridad de la entrega E.
- La distancia se calcula sobre las señales del veredicto, no sobre las filas
  de las matrices de métricas.

## Próxima entrega

**44.24.C.4** (cross-links) y luego **44.24.B** (las frases del veredicto), que
consume el orden y las distancias que esta entrega deja calculados.
