'use client';

import { useDashboardSummary, useReceipts } from '@finanzas/services';
import { useCurrencyStore } from '@finanzas/store';
import { colors, fontSize, fontWeight, formatAmount, spacing } from '@finanzas/ui';

import { Card } from '@/components/ui/card';

export interface StitchTransactionsKpiRowProps {
  currency: string;
  dateFrom: string;
  dateTo: string;
}

/**
 * Fila de 4 KPIs sobre la tabla de Transactions, estilo Stitch:
 *  - Income this period
 *  - Expenses this period
 *  - Net Balance (con signo)
 *  - Pending Clear: tickets en estado `pending`.
 *
 * PHASE-8.3: cuando el toggle global "Convertir todas las monedas"
 * está ON, el endpoint `/dashboard/summary` recibe `target_currency`
 * y agrega cross-currency en SQL convirtiendo cada transacción con la
 * tasa del día de su `occurred_at`. Cuando está OFF, recibe `currency`
 * (legacy) y filtra por moneda activa sin conversión.
 */
export function StitchTransactionsKpiRow({
  currency,
  dateFrom,
  dateTo,
}: StitchTransactionsKpiRowProps) {
  const convertAll = useCurrencyStore((s) => s.convertAll);
  const summaryQuery = useDashboardSummary(
    convertAll
      ? { target_currency: currency, date_from: dateFrom, date_to: dateTo }
      : { currency, date_from: dateFrom, date_to: dateTo },
  );

  const summary = summaryQuery.data;

  const receiptsQuery = useReceipts({ limit: 100 });
  const pendingCount =
    receiptsQuery.data?.items.filter((r) => r.status === 'pending').length ?? 0;

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: spacing.md,
      }}
    >
      <Kpi
        label="Income this period"
        value={summary ? formatAmount(summary.income, currency) : '—'}
        valueColor={colors.text}
      />
      <Kpi
        label="Expenses this period"
        value={summary ? formatAmount(summary.expenses, currency) : '—'}
        valueColor={colors.danger}
      />
      <Kpi
        label="Net Balance"
        value={
          summary
            ? `${Number(summary.balance) >= 0 ? '+' : ''}${formatAmount(summary.balance, currency)}`
            : '—'
        }
        valueColor={
          summary
            ? Number(summary.balance) >= 0
              ? colors.success
              : colors.danger
            : colors.text
        }
      />
      <Kpi
        label="Tickets pendientes"
        value={String(pendingCount)}
        valueColor={pendingCount > 0 ? colors.warning : colors.textMuted}
      />
    </div>
  );
}

function Kpi({
  label,
  value,
  valueColor,
}: {
  label: string;
  value: string;
  valueColor: string;
}) {
  return (
    <Card
      style={{
        backgroundColor: colors.surfaceMuted,
        padding: spacing.md,
        display: 'flex',
        flexDirection: 'column',
        gap: spacing.xs,
      }}
    >
      <span
        style={{
          fontSize: fontSize.xs,
          fontWeight: fontWeight.medium,
          color: colors.textMuted,
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontSize: fontSize.xxl,
          fontWeight: fontWeight.bold,
          color: valueColor,
          letterSpacing: '-0.01em',
          fontVariantNumeric: 'tabular-nums',
          lineHeight: 1.15,
        }}
      >
        {value}
      </span>
    </Card>
  );
}
