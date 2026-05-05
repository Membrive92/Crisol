'use client';

import type { Category, Subscription } from '@finanzas/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  formatDate,
  radius,
  spacing,
} from '@finanzas/ui';

import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

export interface SubscriptionCardProps {
  subscription: Subscription;
  categories: Category[];
  /** Acción primaria (Confirmar para pending, Eliminar para confirmed). */
  primaryAction?: { label: string; onClick: () => void; busy?: boolean };
  /** Acción secundaria (Descartar para pending, etc.). */
  secondaryAction?: { label: string; onClick: () => void; busy?: boolean; danger?: boolean };
}

const CADENCE_LABEL: Record<number, string> = {
  7: 'Semanal',
  14: 'Quincenal',
  30: 'Mensual',
  90: 'Trimestral',
  180: 'Semestral',
  365: 'Anual',
};

function findCategory(categories: Category[], id: string | null): Category | undefined {
  if (!id) return undefined;
  return categories.find((c) => c.id === id);
}

/**
 * Card de una subscripción detectada. Reusable entre las secciones
 * pending/confirmed/dismissed — los callers controlan qué acciones
 * ofrecer.
 */
export function SubscriptionCard({
  subscription: sub,
  categories,
  primaryAction,
  secondaryAction,
}: SubscriptionCardProps) {
  const category = findCategory(categories, sub.category_id);
  const cadenceLabel = CADENCE_LABEL[sub.cadence_days] ?? `${sub.cadence_days}d`;
  const confidencePct = Math.round(sub.confidence * 100);

  return (
    <Card style={{ padding: spacing.md }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: spacing.sm,
          marginBottom: spacing.sm,
        }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <span
            style={{
              fontSize: fontSize.md,
              fontWeight: fontWeight.semibold,
              color: colors.text,
              display: 'block',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {sub.raw_description}
          </span>
          <span style={{ fontSize: fontSize.xs, color: colors.textMuted }}>
            {cadenceLabel} · {category?.name ?? 'Sin categoría'} · confianza{' '}
            {confidencePct}%
          </span>
        </div>
        <span
          style={{
            fontSize: fontSize.md,
            fontWeight: fontWeight.semibold,
            color: colors.text,
            fontVariantNumeric: 'tabular-nums',
            whiteSpace: 'nowrap',
          }}
        >
          {formatAmount(sub.amount, sub.currency)}
        </span>
      </div>

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: spacing.sm,
          padding: `${spacing.xs}px 0`,
          borderTop: `1px solid ${colors.border}`,
          marginTop: spacing.xs,
        }}
      >
        <div style={{ fontSize: fontSize.xs, color: colors.textMuted }}>
          Próximo cargo:{' '}
          <strong style={{ color: colors.text, fontWeight: fontWeight.medium }}>
            {formatDate(sub.next_due)}
          </strong>{' '}
          · {sub.occurrence_count}{' '}
          {sub.occurrence_count === 1 ? 'cargo' : 'cargos'} detectados
        </div>
        <div style={{ display: 'inline-flex', gap: spacing.xs }}>
          {secondaryAction ? (
            <Button
              variant="ghost"
              onClick={secondaryAction.onClick}
              disabled={secondaryAction.busy}
              style={{
                padding: `4px ${spacing.sm}px`,
                color: secondaryAction.danger ? colors.danger : colors.text,
                borderColor: colors.border,
                borderRadius: radius.sm,
              }}
            >
              {secondaryAction.busy ? '…' : secondaryAction.label}
            </Button>
          ) : null}
          {primaryAction ? (
            <Button
              onClick={primaryAction.onClick}
              disabled={primaryAction.busy}
              style={{ padding: `4px ${spacing.sm + 2}px` }}
            >
              {primaryAction.busy ? '…' : primaryAction.label}
            </Button>
          ) : null}
        </div>
      </div>
    </Card>
  );
}
