# PHASE-44.22 — Los tres charts del informe

**Estado**: ✅ implementada (pendiente de mirarla con los ojos)
**Rama**: `main` (push directo)
**Alcance**: sólo web. Sin backend, sin migración, sin tocar el motor.

## Objetivo

El informe tenía siete pestañas con todo el análisis y **todo en tablas**. Era lo
único grande que quedaba del plan de PHASE-44.9. Tres charts, uno por pregunta
que una tabla contesta despacio.

## Qué entra, y por qué esa forma

| Chart | La pregunta que contesta | Forma, y por qué |
|---|---|---|
| **Heatmap de Δ%** (Evolución) | ¿Dónde y cuándo se movió esta empresa? | Rejilla magnitud × ejercicio. Diez magnitudes por cinco años son cincuenta números que hay que leer uno a uno; el color da el patrón de un vistazo |
| **Deriva common-size** (Evolución) | ¿Se está moviendo la estructura de márgenes? | Cuatro líneas sobre un solo eje. La tabla de «% común» contesta cuánto pesó cada cosa; no contesta si se mueve |
| **Dumbbell de stress** (Veredicto) | ¿Cuánto cae la cobertura y sigue cubriendo? | Antes → después por escenario, con la línea del 1,0. Dos barras agrupadas obligarían a medir dos alturas para inferir una diferencia que el segmento ya dibuja |

## El color se calculó, no se eligió a ojo

Las tres decisiones de color salieron del validador, y **dos de ellas
corrigieron lo que yo había escrito**:

1. **La escala del heatmap es verde↔rojo** —la convención de la casa— y sus polos
   están a **ΔE 2,6 bajo protanopía**: un protanope no distingue una caída fuerte
   de un crecimiento fuerte. No se cambia la escala (el resto de la aplicación
   habla ese idioma), se cambia lo que la hace legible: **el valor con su signo
   va impreso en cada celda**, siempre. El color es refuerzo, nunca la fuente.
2. **La paleta de la deriva empezó siendo el cobre de la marca y su tono
   oscuro**. El validador los tumbó a **ΔE 14,3 con visión NORMAL**, por debajo
   del suelo de 15 — no es un problema de daltonismo, es que cualquiera los
   confunde, y eso no lo arregla una etiqueta. Con el morado en su sitio, el peor
   par sube a 17,1 (normal) y 9,6 (deuteranopía).
3. **Las rampas del heatmap se re-escalonaron** hasta que los extremos claros
   despegaron del fondo blanco (2:1), comprobado como rampa ordinal por lado.

## Un bug que cazó su propio test

La escala tenía tres pasos por lado y **dos cortes**, así que el paso más claro
de cada rampa era inalcanzable: un color declarado y muerto. Lo destapó el test
que comprobaba la correspondencia fondo↔tinta. Tres bandas exigen tres cortes
(±2% ruido, ±10% movimiento, ±25% movimiento que hay que explicar).

## Decisiones que conviene conocer

- **El heatmap es una `<table>` de verdad**, no un lienzo: navegable, con
  cabeceras de fila y columna y legible por un lector de pantalla. Eso cubre a la
  vez la forma y el requisito de «vista de tabla» que un chart de escala continua
  necesita.
- **El dumbbell es SVG a mano.** Tres filas de dos puntos y un segmento es menos
  código que configurar Recharts para que finja ser esto, y así el `<title>` de
  cada marca lleva la frase que el motor ya redactó.
- **La escala divergente vive en `packages/ui`** (capa pura, ADR-0001): el día
  que móvil pinte el heatmap, los cortes y los colores ya están decididos. Dos
  implementaciones del mismo semáforo acabarían discrepando sobre la misma
  empresa.
- **La rejilla de la deriva es sólida.** Los otros seis charts de la aplicación
  la llevan discontinua, que se lee como umbral cuando sólo es una guía. Aquí se
  estrena la regla; alinear los antiguos queda en el backlog.

## Verificación

- `typecheck` · `lint` · `knip` verdes; **161 tests** en web, con nueve nuevos
  (cinco del heatmap, cuatro del dumbbell) y cuatro más de la escala en `ui`.
- Lo que prueban no es que devuelvan colores: que el signo viaja, que el primer
  ejercicio no se pinta porque no tiene con qué compararse, que una serie sin
  datos no ocupa una fila muda, y que la línea del 1,0 entra en el lienzo
  **aunque todos los escenarios queden por debajo** — si la escala se ajustara
  sólo a los datos, la única lectura que importa se saldría del dibujo.

## Limitaciones conocidas

- **No se han mirado con los ojos.** El método tiene un último paso —renderizar y
  mirar— que exige la app levantada con un análisis real. Va con tu prueba
  manual: hay que comprobar colisiones de etiquetas, desbordes y que la etiqueta
  directa del último punto no se salga del lienzo en una serie corta.
- **Sólo web.** Móvil sigue con las tablas.
- El heatmap arranca en el SEGUNDO ejercicio a propósito: el primero no tiene con
  qué compararse. Con una serie de un año, lo dice en vez de pintar una rejilla
  vacía.
