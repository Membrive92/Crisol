'use client';

import type { DashboardSummary } from '@finanzas/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';
import { formatAmount } from '@finanzas/ui';

import { Card } from '@/components/ui/card';
import { TrendingDownIcon, TrendingUpIcon } from '@/components/ui/icons';

export interface StitchKeyMetricsProps {
  summary: DashboardSummary | undefined;
  currency: string;
}

/**
 * Dos cards apiladas en la columna derecha del bento de Análisis:
 *  - Net Cash Flow (= balance) con delta vs periodo previo.
 *  - Saving Rate (= balance / income) con barra de progreso.
 */
export function StitchKeyMetrics({ summary, currency }: StitchKeyMetricsProps) {
  const balance = summary ? Number(summary.balance) : 0;
  const previousBalance = summary?.previous_period_balance != null ? Number(summary.previous_period_balance) : null;
  const incomeNum = summary ? Number(summary.income) : 0;
  const savingRate = incomeNum > 0 ? (balance / incomeNum) * 100 : null;
  const balanceDelta =
    previousBalance !== null && previousBalance !== 0
      ? ((balance - previousBalance) / Math.abs(previousBalance)) * 100
      : null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
      <Card style={{ padding: spacing.lg }}>
        <span
          style={{
            fontSize: fontSize.xs,
            fontWeight: fontWeight.medium,
            color: colors.textMuted,
            display: 'block',
            marginBottom: spacing.xs,
          }}
        >
          Flujo de caja neto
        </span>
        <span
          style={{
            display: 'block',
            fontSize: fontSize.xxl,
            fontWeight: fontWeight.bold,
            color: balance >= 0 ? colors.success : colors.danger,
            letterSpacing: '-0.01em',
            fontVariantNumeric: 'tabular-nums',
            lineHeight: 1.15,
          }}
        >
          {summary
            ? `${balance >= 0 ? '+' : ''}${formatAmount(summary.balance, currency)}`
            : '—'}
        </span>
        {balanceDelta !== null ? (
          <div
            style={{
              marginTop: spacing.md,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              color: balanceDelta >= 0 ? colors.success : colors.danger,
              fontSize: fontSize.xs,
              fontWeight: fontWeight.semibold,
            }}
          >
            {balanceDelta >= 0 ? <TrendingUpIcon size={14} /> : <TrendingDownIcon size={14} />}
            {balanceDelta >= 0 ? '+' : ''}
            {balanceDelta.toFixed(1)}% vs periodo anterior
          </div>
        ) : (
          <span
            style={{
              marginTop: spacing.md,
              display: 'inline-block',
              fontSize: fontSize.xs,
              color: colors.textSubtle,
            }}
          >
            Sin periodo previo para comparar
          </span>
        )}
      </Card>

      <Card style={{ padding: spacing.lg }}>
        <span
          style={{
            fontSize: fontSize.xs,
            fontWeight: fontWeight.medium,
            color: colors.textMuted,
            display: 'block',
            marginBottom: spacing.xs,
          }}
        >
          Tasa de ahorro
        </span>
        <span
          style={{
            display: 'block',
            fontSize: fontSize.xxl,
            fontWeight: fontWeight.bold,
            color: savingRate !== null && savingRate >= 0 ? colors.primary : colors.danger,
            letterSpacing: '-0.01em',
            fontVariantNumeric: 'tabular-nums',
            lineHeight: 1.15,
          }}
        >
          {savingRate !== null ? `${savingRate.toFixed(1)}%` : '—'}
        </span>
        <div
          style={{
            marginTop: spacing.md,
            width: '100%',
            height: 6,
            backgroundColor: colors.surfaceMuted,
            borderRadius: radius.sm,
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              width: savingRate !== null ? `${Math.max(0, Math.min(100, savingRate))}%` : '0%',
              height: '100%',
              backgroundColor: colors.primary,
              transition: 'width 200ms ease',
            }}
          />
        </div>
      </Card>
    </div>
  );
}
