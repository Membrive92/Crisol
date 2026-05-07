'use client';

import type { Category, FixedExpense } from '@finanzas/types';
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

export interface FixedExpenseCardProps {
  fixedExpense: FixedExpense;
  categories: Category[];
  /** Acción primaria (Confirmar para pending, Pausar para confirmed, etc.). */
  primaryAction?: { label: string; onClick: () => void; busy?: boolean };
  /** Acción secundaria (Descartar para pending, Cancelar para confirmed, etc.). */
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
 * Card de un gasto fijo detectado. Reusable entre las secciones
 * pending/confirmed/paused/cancelled/dismissed — los callers
 * controlan qué acciones ofrecer.
 */
export function FixedExpenseCard({
  fixedExpense: item,
  categories,
  primaryAction,
  secondaryAction,
}: FixedExpenseCardProps) {
  const category = findCategory(categories, item.category_id);
  const cadenceLabel = CADENCE_LABEL[item.cadence_days] ?? `${item.cadence_days}d`;
  const confidencePct = Math.round(item.confidence * 100);

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
            {item.raw_description}
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
          {formatAmount(item.amount, item.currency)}
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
            {formatDate(item.next_due)}
          </strong>{' '}
          · {item.occurrence_count}{' '}
          {item.occurrence_count === 1 ? 'cargo' : 'cargos'} detectados
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
