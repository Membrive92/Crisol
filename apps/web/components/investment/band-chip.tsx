'use client';

import { bandColors, bandLabel, fontSize, fontWeight, radius, spacing } from '@crisol/ui';
import type { MetricBand } from '@crisol/types';

// `bandColors` y `bandLabel` viven en `@crisol/ui` desde PHASE-44.8: el móvil
// necesita el MISMO semáforo y duplicarlo es cómo una pantalla acaba pintando de
// verde lo que la otra pinta de gris. Aquí sólo queda el componente web.
export { bandColors, bandLabel };

export interface BandChipProps {
  band: MetricBand | null;
  label?: string | undefined;
  /** Título accesible: normalmente el corte contra el que se juzga. */
  title?: string | undefined;
}

export function BandChip({ band, label, title }: BandChipProps) {
  const { fg, bg } = bandColors(band);
  return (
    <span
      title={title}
      style={{
        color: fg,
        backgroundColor: bg,
        borderRadius: radius.sm,
        padding: `2px ${spacing.sm}px`,
        fontSize: fontSize.xs,
        fontWeight: fontWeight.semibold,
        whiteSpace: 'nowrap',
      }}
    >
      {label ?? bandLabel(band)}
    </span>
  );
}

/** Punto de color del semáforo, para cabeceras densas (el hero). */
export function BandDot({
  band,
  title,
}: {
  band: MetricBand | null;
  // `| undefined` explícito: con `exactOptionalPropertyTypes` una prop opcional
  // NO acepta un `undefined` pasado a mano, y aquí el padre lo hace.
  title?: string | undefined;
}) {
  const { fg } = bandColors(band);
  return (
    <span
      title={title}
      aria-hidden
      style={{
        display: 'inline-block',
        width: 8,
        height: 8,
        borderRadius: '50%',
        backgroundColor: fg,
        flexShrink: 0,
      }}
    />
  );
}
