'use client';

import type { ReceiptStatus } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

const STATUS_LABEL: Record<ReceiptStatus, string> = {
  pending: 'Pendiente',
  confirmed: 'Confirmado',
  rejected: 'Rechazado',
};

const STATUS_COLOR: Record<ReceiptStatus, { bg: string; fg: string }> = {
  pending: { bg: colors.primarySoft, fg: colors.primary },
  confirmed: { bg: colors.successSoft, fg: colors.success },
  rejected: { bg: colors.dangerSoft, fg: colors.danger },
};

export interface ReceiptStatusBadgeProps {
  status: ReceiptStatus;
}

export function ReceiptStatusBadge({ status }: ReceiptStatusBadgeProps) {
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
