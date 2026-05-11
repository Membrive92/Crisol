'use client';

import type { TransactionSource } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

const LABELS: Record<TransactionSource, string> = {
  manual: 'Manual',
  import: 'Importado',
  receipt: 'Ticket',
  expected: 'Esperada',
};

interface Palette {
  bg: string;
  fg: string;
}

function paletteFor(source: TransactionSource): Palette {
  switch (source) {
    case 'import':
      return { bg: colors.primarySoft, fg: colors.primary };
    case 'receipt':
      return { bg: colors.successSoft, fg: colors.success };
    case 'expected':
      return { bg: colors.warningSoft, fg: colors.warning };
    case 'manual':
    default:
      return { bg: colors.surfaceMuted, fg: colors.textMuted };
  }
}

export interface OriginBadgeProps {
  source: TransactionSource;
}

/**
 * Chip que indica de dónde proviene una transacción: entrada manual,
 * importación CSV/PDF o ticket extraído con IA. Tipografía `overline`,
 * paleta tonal por origen.
 */
export function OriginBadge({ source }: OriginBadgeProps) {
  const palette = paletteFor(source);
  return (
    <span
      style={{
        display: 'inline-block',
        padding: `${spacing.xs / 2}px ${spacing.sm}px`,
        backgroundColor: palette.bg,
        color: palette.fg,
        borderRadius: radius.sm,
        fontSize: fontSize.xs,
        fontWeight: fontWeight.semibold,
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
        whiteSpace: 'nowrap',
      }}
    >
      {LABELS[source]}
    </span>
  );
}
