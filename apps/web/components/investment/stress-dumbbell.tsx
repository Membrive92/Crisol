'use client';

import { colors, fontSize, fontWeight, spacing } from '@crisol/ui';
import type { StressScenario } from '@crisol/types';

/**
 * Los escenarios de stress, antes → después (PHASE-44.22).
 *
 * La forma la decide el trabajo del lector: comparar **el mismo indicador antes
 * y después, por escenario**. Eso es un dumbbell — dos puntos unidos, un hue en
 * dos tonos— y no dos barras agrupadas, que obligan a medir dos alturas para
 * inferir una diferencia que el segmento ya dibuja.
 *
 * Lo que decide de verdad está en la línea del 1,0: por debajo, la caja libre
 * del escenario **no cubre el dividendo**. Un dumbbell sin esa referencia
 * enseñaría movimiento sin consecuencia.
 *
 * SVG a mano y no Recharts: tres filas de dos puntos y un segmento es menos
 * código que configurar un `ComposedChart` para que finja ser esto, y así el
 * `<title>` de cada marca lleva la frase que el motor ya redactó.
 */
export function StressDumbbell({ scenarios }: { scenarios: StressScenario[] }) {
  const rows = scenarios
    .map((scenario) => ({
      scenario,
      before: toNumber(scenario.coverage_before),
      after: toNumber(scenario.coverage_after),
    }))
    .filter((row) => row.before !== null && row.after !== null);

  if (rows.length === 0) return null;

  // La escala nace en 0 y llega al peor caso entre el mayor valor y la propia
  // línea de corte: si todos los escenarios quedaran por debajo de 1,0, una
  // escala ajustada a los datos dejaría la referencia fuera del dibujo y con
  // ella la única lectura que importa.
  const max = Math.max(1.15, ...rows.flatMap((r) => [r.before ?? 0, r.after ?? 0])) * 1.1;
  const width = 560;
  const left = 190;
  const rowHeight = 44;
  const height = rows.length * rowHeight + 28;
  const x = (value: number) => left + (value / max) * (width - left - 24);

  return (
    <div style={{ overflowX: 'auto' }}>
      {/* Ancho FIJO y scroll en el contenedor, como la heatmap. La primera
          corrección escalaba el dibujo con `viewBox`, y con él escalaban los
          rótulos: a 390 px quedaban a 5-6 px, ilegibles. Antes de eso,
          `maxWidth:'100%'` sin `viewBox` encogía la caja pero no el dibujo y
          recortaba la línea del 1,0. Un dibujo de 560 px que se desplaza es
          la única versión que se lee en todas las pantallas. */}
      <svg
        width={width}
        height={height}
        role="img"
        aria-label="Cobertura del dividendo antes y después de cada escenario"
        style={{ display: 'block', minWidth: width }}
      >
        {/* La línea del 1,0: por debajo, el escenario deja de cubrir. */}
        <line
          x1={x(1)}
          x2={x(1)}
          y1={4}
          y2={rows.length * rowHeight + 8}
          stroke={colors.danger}
          strokeWidth={2}
          strokeDasharray="4 3"
        />
        <text
          x={x(1)}
          y={rows.length * rowHeight + 22}
          textAnchor="middle"
          fontSize={10}
          fill={colors.danger}
        >
          1,0 — deja de cubrir
        </text>

        {rows.map((row, i) => {
          const y = i * rowHeight + 22;
          const before = row.before as number;
          const after = row.after as number;
          const worse = after < before;
          return (
            <g key={row.scenario.key}>
              <title>{row.scenario.sentence}</title>
              <text x={0} y={y + 4} fontSize={11} fill={colors.textMuted}>
                {row.scenario.parameter}
              </text>
              <line
                x1={x(Math.min(before, after))}
                x2={x(Math.max(before, after))}
                y1={y}
                y2={y}
                stroke={colors.border}
                strokeWidth={2}
              />
              {/* Antes: el tono claro del mismo hue. Después: el oscuro — el
                  que el ojo persigue, que es el valor que se juzga. */}
              <circle
                cx={x(before)}
                cy={y}
                r={5}
                fill="#f0c8ab"
                stroke={colors.surface}
                strokeWidth={2}
              />
              <circle
                cx={x(after)}
                cy={y}
                r={6}
                fill={after < 1 ? colors.danger : worse ? colors.primary : colors.success}
                stroke={colors.surface}
                strokeWidth={2}
              />
              <text
                x={x(after) + 12}
                y={y + 4}
                fontSize={11}
                fill={colors.text}
                fontWeight={fontWeight.semibold}
              >
                {after.toLocaleString('es-ES', { maximumFractionDigits: 2 })}×
              </text>
            </g>
          );
        })}
      </svg>
      <div
        style={{
          display: 'flex',
          gap: spacing.md,
          color: colors.textMuted,
          fontSize: fontSize.xs,
          marginTop: spacing.xs,
        }}
      >
        {/* La leyenda dice lo que el dibujo hace: el punto de «después» usa el
            color de ESTADO —rojo si deja de cubrir— y no un color de serie.
            Anunciarlo con un solo tono sería una leyenda que no casa con las
            marcas. */}
        <Dot color="#f0c8ab" label="cobertura actual" />
        <Dot color={colors.success} label="tras el escenario: sigue cubriendo" />
        <Dot color={colors.danger} label="deja de cubrir" />
        <span>· escenarios hipotéticos, no previsiones</span>
      </div>
    </div>
  );
}

function Dot({ color, label }: { color: string; label: string }) {
  return (
    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      <span
        aria-hidden
        style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: color }}
      />
      {label}
    </span>
  );
}

function toNumber(value: string | null): number | null {
  if (value === null) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}
