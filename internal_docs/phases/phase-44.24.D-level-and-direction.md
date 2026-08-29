# PHASE-44.24.D — Nivel y dirección

**Estado**: 🚧 pendiente prueba manual
**Rama**: `main` (push directo)
**Fecha**: 2026-08-27

## Objetivo

El informe pintaba el **nivel** de cada métrica en cada ejercicio y ninguna
**dirección**. Un Z''-Score de 2,6 en verde y un Z''-Score de 2,6 que viene de
3,1 → 2,9 → 2,8 cuentan historias opuestas, y la tabla las presentaba igual.

## Qué se implementó

- **`sparklineOf`** (`packages/ui/src/investment-sparkline.ts`): la serie de una
  fila reducida a puntos normalizados más una **etiqueta de texto**, que es lo
  que oye un lector de pantalla. Capa PURA: quien dibuja es cada app con sus
  primitivas (SVG en web, `react-native-svg` en móvil), pero la frase la compone
  `@crisol/ui` una sola vez.
- **Columna «Tendencia»** en las cinco matrices de las **dos** apps. La columna
  existe si alguna fila trae la clave, lo que obliga a mover la cabecera, el
  relleno de las filas de grupo y los dos `colSpan`.
- **`scoreBreakdownRows`** (`investment-score-rows.ts`): el desglose de un score
  forense con la **variación frente al ejercicio anterior** por variable. Un DSRI
  de 1,08 no dice nada suelto; que venga de 0,98 sí — es el movimiento lo que el
  modelo de Beneish detecta.
- **Móvil gana el desglose de scores, que no tenía ninguno**: los ocho salían
  como un número por año y sus **27 variables** no se veían por ningún sitio.

## Decisiones

| Decisión | Por qué |
|---|---|
| `null` con menos de **3** puntos | Dos puntos son una recta: afirmaría una tendencia que nadie ha medido. Y `null` NO se pinta en blanco —se dice «serie corta»—, porque una celda vacía se lee como «no calculable», que es una afirmación sobre los datos de la empresa. |
| Los huecos se **omiten**, no se interpolan | Una línea continua sobre un año que nadie midió es la mentira que el motor evita con `not_computable`. |
| Banda plana del **2 %** | Por debajo es ruido; llamar «descendente» a una serie plana afirma una tendencia inexistente. Mismo corte que la escala de variaciones de PHASE-44.22. |
| `delta: null` ≠ `'='` | `null` es «no se puede comparar» (no hay ejercicio anterior con desglose). Un `=` ahí afirmaría una comparación que no se ha hecho. |
| La delta compara contra el **anterior PRESENTE**, no contra `year − 1` | Con un hueco, `year − 1` no existe y la comparación se perdería entera aunque haya con qué comparar. |
| Un check dice si **cambió**, no una magnitud | Un booleano no tiene delta; lo que se puede decir es «nuevo» / «perdido». Repetir «=» en cada check es ruido. |

## Lo que destaparon las sondas

Siete sondas, las siete muerden. Dos hallazgos que **no** venían de leer el
código:

1. **La etiqueta nombraba un rango continuo con un hueco dentro.** El test dio
   `serie 2020-2023: 1,00×; 3,00×; 4,00×` — un rango de cuatro años con tres
   valores. La comprobación de «contiguo» estaba escrita como «cada índice tiene
   año», que se cumple igual con un salto. Ahora: rango sólo si los ejercicios
   son consecutivos; si no, se enumeran.
2. **El filtro por ESTADO no se ejercitaba.** La sonda «interpolar los huecos»
   no mordía: hoy el motor siempre empareja `not_computable`/`not_applicable`
   con `value: null`, así que la guarda de valor ausente lo tapaba. El test
   pasaba por un camino distinto del que decía medir. Reescrito con un
   `not_applicable` que **trae número** — el caso que la calibración sectorial
   de PHASE-44.21 hace posible, porque apaga 33 métricas dejándoles su valor.

## Archivos clave

- `packages/ui/src/investment-sparkline.ts` — la serie, pura.
- `packages/ui/src/investment-score-rows.ts` — el desglose con delta.
- `apps/web/components/investment/year-matrix.tsx` · `apps/mobile/…/year-matrix.tsx`
- `apps/web/components/investment/score-breakdown-card.tsx` — consume el nuevo
  view-model; `ScoreCard` en `apps/mobile/…/report-tabs.tsx` es su hermana RN.

## Verificación

- 19 tests nuevos (`investment-sparkline.test.ts`, `investment-score-rows.test.ts`,
  la columna de tendencia en `year-matrix.test.tsx`).
- **7 sondas, las 7 muerden.**
- `pnpm typecheck` · `pnpm lint` · web 250 · ui 210 · móvil 83.

## Limitaciones conocidas

- La serie del score en móvil se dibuja en 36×12: en un teléfono no cabe más, y
  el detalle vive en la matriz de abajo.
- No hay eje ni escala en la sparkline **a propósito**: el valor por año está en
  la misma fila, y una escala en 40 píxeles sería decorativa.
