'use client';

import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';
import type { MetricBand } from '@crisol/types';

/**
 * El semáforo del módulo. Una banda `null` es GRIS y dice «sin banda» — nunca
 * verde: `ThresholdSpec.band_for` del engine documenta que `None` no significa
 * «sana», sino «no hay banda que aplicar».
 */
export function bandColors(band: MetricBand | null): { fg: string; bg: string } {
  if (band === 'healthy') return { fg: colors.success, bg: colors.successSoft };
  if (band === 'caution') return { fg: colors.warning, bg: colors.warningSoft };
  if (band === 'stressed') return { fg: colors.danger, bg: colors.dangerSoft };
  return { fg: colors.textMuted, bg: colors.surfaceMuted };
}

const BAND_LABEL: Record<MetricBand, string> = {
  healthy: 'Sano',
  caution: 'Vigilar',
  stressed: 'Riesgo',
};

export function bandLabel(band: MetricBand | null): string {
  return band ? BAND_LABEL[band] : 'Sin banda';
}

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
