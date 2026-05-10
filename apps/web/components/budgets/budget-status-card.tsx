'use client';

import type { BudgetStatusItem, Category } from '@finanzas/types';
import { colors, fontSize, fontWeight, formatAmount, radius, spacing } from '@finanzas/ui';

import { Card } from '@/components/ui/card';

export interface BudgetStatusCardProps {
  item: BudgetStatusItem;
  categories: Category[];
}

function findCategory(categories: Category[], id: string | null): Category | undefined {
  if (!id) return undefined;
  return categories.find((c) => c.id === id);
}

function paletteFor(status: BudgetStatusItem['status']): { accent: string; soft: string } {
  switch (status) {
    case 'over':
      return { accent: colors.danger, soft: colors.dangerSoft };
    case 'warning':
      return { accent: colors.warning, soft: colors.warningSoft };
    case 'ok':
    default:
      return { accent: colors.success, soft: colors.successSoft };
  }
}

/**
 * Tarjeta de un budget activo con su estado del mes en curso. Pinta:
 * - Categoría (o "Global" si `category_id IS NULL`).
 * - Spent vs límite con el delta.
 * - Barra de progreso cap a 100% (el `over` se distingue por color y
 *   por el badge "X% usado", no por la barra).
 * - Badge de status con palette por kind.
 */
export function BudgetStatusCard({ item, categories }: BudgetStatusCardProps) {
  const { budget, spent_this_month, remaining, percent_used, status } = item;
  const palette = paletteFor(status);
  const category = findCategory(categories, budget.category_id);
  const label = category?.name ?? 'Global (todas las categorías)';
  const emoji = category?.icon ?? null;
  const accent = category?.color ?? null;
  const cappedPercent = Math.min(percent_used, 100);

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
        <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm, minWidth: 0 }}>
          {accent ? (
            <span
              aria-hidden
              style={{
                width: 28,
                height: 28,
                borderRadius: '50%',
                backgroundColor: accent,
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              {emoji ? <span style={{ fontSize: fontSize.sm, lineHeight: 1 }}>{emoji}</span> : null}
            </span>
          ) : null}
          <div style={{ minWidth: 0 }}>
            <span
              style={{
                fontSize: fontSize.sm,
                fontWeight: fontWeight.semibold,
                color: colors.text,
                display: 'block',
              }}
            >
              {label}
            </span>
            <span style={{ fontSize: fontSize.xs, color: colors.textMuted }}>
              Límite mensual {formatAmount(budget.amount, budget.currency)}
            </span>
          </div>
        </div>
        <span
          style={{
            backgroundColor: palette.soft,
            color: palette.accent,
            border: `1px solid ${palette.accent}`,
            borderRadius: radius.sm,
            padding: '2px 8px',
            fontSize: 11,
            fontWeight: fontWeight.semibold,
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
            whiteSpace: 'nowrap',
          }}
        >
          {percent_used.toFixed(0)}% · {status}
        </span>
      </div>

      <div
        aria-hidden
        style={{
          width: '100%',
          height: 8,
          backgroundColor: colors.surfaceMuted,
          borderRadius: radius.sm,
          overflow: 'hidden',
          marginBottom: spacing.sm,
        }}
      >
        <div
          style={{
            width: `${cappedPercent}%`,
            height: '100%',
            backgroundColor: palette.accent,
            transition: 'width 200ms ease',
          }}
        />
      </div>

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: fontSize.xs,
          color: colors.textMuted,
        }}
      >
        <span>
          Gastado{' '}
          <strong style={{ color: colors.text }}>
            {formatAmount(spent_this_month, budget.currency)}
          </strong>
        </span>
        <span>
          {Number(remaining) >= 0 ? 'Restante' : 'Excedido'}{' '}
          <strong style={{ color: Number(remaining) >= 0 ? colors.text : colors.danger }}>
            {formatAmount(
              (Number(remaining) >= 0 ? remaining : `-${remaining}`).toString(),
              budget.currency,
            )}
          </strong>
        </span>
      </div>

      {item.unconvertible_count > 0 ? (
        <div
          style={{
            marginTop: spacing.xs,
            fontSize: fontSize.xs,
            color: colors.warning,
          }}
          title="Estas transacciones se quedaron fuera del cálculo porque no hay tasa de cambio disponible para su día."
        >
          ≈ {item.unconvertible_count}{' '}
          {item.unconvertible_count === 1 ? 'transacción' : 'transacciones'}{' '}
          sin tasa
        </div>
      ) : null}
    </Card>
  );
}
