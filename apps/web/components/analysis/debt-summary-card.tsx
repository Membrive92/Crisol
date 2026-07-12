'use client';

import { useDebtHealth } from '@crisol/services';
import { useCurrencyStore } from '@crisol/store';
import type { DtiStatus } from '@crisol/types';
import { colors, fontSize, fontWeight, formatAmount, spacing } from '@crisol/ui';

import { Card, CardTitle } from '@/components/ui/card';
import { HeartPulseIcon } from '@/components/ui/icons';

const EFFORT_LABEL: Record<DtiStatus, string> = {
  healthy: 'Saludable',
  caution: 'Precaución',
  stressed: 'Sobreendeudado',
  unknown: 'Sin datos',
};
const EFFORT_COLOR: Record<DtiStatus, string> = {
  healthy: colors.success,
  caution: colors.warning,
  stressed: colors.danger,
  unknown: colors.textSubtle,
};

/**
 * PHASE-37.2 — Resumen de deuda condensado (parte ② del antiguo PositionHero):
 * deuda total + tasa de esfuerzo + cuota mensual + APR medio. Los próximos
 * vencimientos llegan en 37.4 (month-outlook).
 */
export function DebtSummaryCard() {
  const storeCurrency = useCurrencyStore((s) => s.currency);
  const convertAll = useCurrencyStore((s) => s.convertAll);
  const targetCurrency = convertAll ? storeCurrency : undefined;
  const debtQuery = useDebtHealth(targetCurrency ? { targetCurrency } : {});
  const debt = debtQuery.data;
  const currency = debt?.reference_currency ?? storeCurrency;

  const effort = debt?.dti_ratio;
  const status = debt?.dti_status ?? 'healthy';

  return (
    <Card style={{ padding: spacing.lg, height: '100%' }}>
      <header style={{ display: 'flex', alignItems: 'center', gap: spacing.sm, marginBottom: spacing.md }}>
        <HeartPulseIcon size={16} />
        <CardTitle>Deuda</CardTitle>
        {debt ? (
          <span
            style={{
              marginLeft: 'auto',
              fontSize: 11,
              fontWeight: fontWeight.semibold,
              color: EFFORT_COLOR[status],
              backgroundColor: colors.surfaceMuted,
              padding: '2px 8px',
              borderRadius: 999,
            }}
          >
            {EFFORT_LABEL[status]}
          </span>
        ) : null}
      </header>

      {debtQuery.isLoading ? (
        <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>Cargando…</p>
      ) : !debt ? (
        <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
          Sin deuda registrada.
        </p>
      ) : (
        <>
          <span
            style={{
              display: 'block',
              fontSize: fontSize.xxl,
              fontWeight: fontWeight.bold,
              color: colors.text,
              fontVariantNumeric: 'tabular-nums',
              letterSpacing: '-0.01em',
              lineHeight: 1.1,
            }}
          >
            {formatAmount(debt.total_liabilities, currency)}
          </span>
          <span style={{ fontSize: fontSize.xs, color: colors.textMuted }}>deuda viva total</span>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: spacing.md,
              marginTop: spacing.md,
              paddingTop: spacing.md,
              borderTop: `1px solid ${colors.border}`,
            }}
          >
            <Kpi
              label="Tasa de esfuerzo"
              value={effort != null ? `${(effort * 100).toFixed(1)} %` : '—'}
              valueColor={EFFORT_COLOR[status]}
            />
            <Kpi label="Cuota mensual" value={formatAmount(debt.monthly_debt_payment, currency)} />
            <Kpi
              label="APR medio"
              value={debt.weighted_apr != null ? `${(debt.weighted_apr * 100).toFixed(2)} %` : '—'}
            />
            <Kpi label="Intereses YTD" value={formatAmount(debt.interest_paid_ytd, currency)} />
          </div>
        </>
      )}
    </Card>
  );
}

function Kpi({ label, value, valueColor }: { label: string; value: string; valueColor?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
      <span
        style={{
          fontSize: 10,
          fontWeight: fontWeight.semibold,
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
          color: colors.textMuted,
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontSize: fontSize.md,
          fontWeight: fontWeight.semibold,
          color: valueColor ?? colors.text,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {value}
      </span>
    </div>
  );
}
