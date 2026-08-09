'use client';

import { colors, deltaLegend, deltaStep, fontSize, fontWeight, radius, spacing } from '@crisol/ui';
import type { HorizontalSeries } from '@crisol/types';

/**
 * Heatmap de variaciones interanuales — magnitud × ejercicio (PHASE-44.22).
 *
 * La evolutiva ya publicaba estas variaciones, pero sólo como números en una
 * tabla: diez magnitudes por cinco ejercicios son cincuenta celdas que hay que
 * leer una a una para ver el patrón. Un heatmap responde de un vistazo la
 * pregunta que la tabla contesta despacio: **dónde y cuándo se movió esta
 * empresa**.
 *
 * ## El número va impreso en cada celda, y no es decorativo
 *
 * Los polos de la escala son el verde y el rojo de la casa. Medido con el
 * simulador de Machado-Oliveira-Fernandes, un protanope los ve a **ΔE 2,6**: no
 * los distingue. Con el valor y su signo dentro, el color refuerza una lectura
 * que ya está completa sin él. Quitar los números para «que se vea más limpio»
 * dejaría la tabla mintiendo a una de cada doce personas.
 *
 * No es un chart de Recharts a propósito: una rejilla es una rejilla, y CSS
 * grid la hace accesible (es una `<table>` de verdad, navegable y legible por un
 * lector de pantalla) sin cargar una librería para dibujar rectángulos.
 */
export function DeltaHeatmap({
  series,
  years,
}: {
  series: HorizontalSeries[];
  years: number[];
}) {
  const withData = series.filter((s) => s.points.some((p) => p.yoy !== null));
  if (withData.length === 0 || years.length < 2) {
    return (
      <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
        Hacen falta al menos dos ejercicios consecutivos para que haya variación que medir.
      </p>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
      <div style={{ overflowX: 'auto' }}>
        <table
          style={{
            borderCollapse: 'separate',
            // 2px de aire entre celdas: sin él, dos fondos contiguos del mismo
            // tono se leen como una sola mancha.
            borderSpacing: 2,
            fontSize: fontSize.xs,
            minWidth: 520,
          }}
        >
          <caption style={visuallyHidden}>
            Variación interanual de cada magnitud, por ejercicio
          </caption>
          <thead>
            <tr>
              <th scope="col" style={{ ...headerCell, textAlign: 'left' }}>
                Magnitud
              </th>
              {years.slice(1).map((year) => (
                <th key={year} scope="col" style={headerCell}>
                  {year}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {withData.map((row) => (
              <tr key={row.key}>
                <th scope="row" style={{ ...headerCell, textAlign: 'left', whiteSpace: 'nowrap' }}>
                  {row.label}
                </th>
                {years.slice(1).map((year) => {
                  const point = row.points.find((p) => p.fiscal_year === year);
                  const yoy = point?.yoy == null ? null : Number(point.yoy);
                  const step = deltaStep(yoy);
                  return (
                    <td
                      key={year}
                      style={{
                        backgroundColor: step.background,
                        color: step.foreground,
                        borderRadius: radius.sm,
                        padding: `${spacing.xs}px ${spacing.sm}px`,
                        textAlign: 'right',
                        fontVariantNumeric: 'tabular-nums',
                        minWidth: 72,
                      }}
                      title={`${row.label} · ${year}`}
                    >
                      {formatDelta(yoy)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: spacing.sm,
          color: colors.textMuted,
          fontSize: fontSize.xs,
        }}
      >
        {deltaLegend().map((entry) => (
          <span key={entry.label} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span
              aria-hidden
              style={{
                width: 12,
                height: 12,
                borderRadius: 3,
                backgroundColor: entry.step.background,
                border: `1px solid ${colors.border}`,
              }}
            />
            {entry.label}
          </span>
        ))}
        <span>· celda vacía: sin dato con el que comparar, que no es un cero</span>
      </div>
    </div>
  );
}

/** `0.1234` → `+12,3%`. El signo va SIEMPRE: es la mitad de la información. */
function formatDelta(yoy: number | null): string {
  if (yoy === null || !Number.isFinite(yoy)) return '';
  const pct = (yoy * 100).toLocaleString('es-ES', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
  return yoy > 0 ? `+${pct}%` : `${pct}%`;
}

const headerCell: React.CSSProperties = {
  color: colors.textMuted,
  fontWeight: fontWeight.semibold,
  fontSize: fontSize.xs,
  padding: `${spacing.xs}px ${spacing.sm}px`,
  textAlign: 'right',
};

const visuallyHidden: React.CSSProperties = {
  position: 'absolute',
  width: 1,
  height: 1,
  padding: 0,
  margin: -1,
  overflow: 'hidden',
  clip: 'rect(0 0 0 0)',
  whiteSpace: 'nowrap',
  border: 0,
};
