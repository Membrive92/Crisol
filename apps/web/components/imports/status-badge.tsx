'use client';

import type { ImportJobStatus } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

const STATUS_LABEL: Record<ImportJobStatus, string> = {
  pending: 'Pendiente',
  processing: 'Procesando',
  preview: 'En revisión',
  completed: 'Completado',
  failed: 'Fallido',
};

const STATUS_COLOR: Record<ImportJobStatus, { bg: string; fg: string }> = {
  pending: { bg: colors.surfaceMuted, fg: colors.textMuted },
  processing: { bg: colors.primarySoft, fg: colors.primary },
  preview: { bg: colors.primarySoft, fg: colors.primary },
  completed: { bg: colors.successSoft, fg: colors.success },
  failed: { bg: colors.dangerSoft, fg: colors.danger },
};

export interface StatusBadgeProps {
  status: ImportJobStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const palette = STATUS_COLOR[status];
  return (
    <span
      style={{
        display: 'inline-block',
        padding: `${spacing.xs}px ${spacing.sm}px`,
        backgroundColor: palette.bg,
        color: palette.fg,
        borderRadius: radius.sm,
        fontSize: fontSize.xs,
        fontWeight: fontWeight.semibold,
        textTransform: 'uppercase',
        letterSpacing: 0.5,
      }}
    >
      {STATUS_LABEL[status]}
    </span>
  );
}
