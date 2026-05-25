'use client';

import type { DebtTimeRange } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
} from '@crisol/ui';

import { Card } from '@/components/ui/card';

export interface PaymentsSummaryCardProps {
  range: DebtTimeRange;
  onRangeChange: (range: DebtTimeRange) => void;
  totalPayments: string;
  interestsAndFees: string;
  capitalAmortized: string;
  currency: string;
  isLoading: boolean;
}

const RANGE_LABEL: Record<DebtTimeRange, string> = {
  ytd: 'YTD',
  '12m': '12 meses',
  month: 'Este mes',
};

const RANGE_TITLE: Record<DebtTimeRange, string> = {
  ytd: 'Pagos a deuda — año en curso',
  '12m': 'Pagos a deuda — últimos 12 meses',
  month: 'Pagos a deuda — este mes',
};

/**
 * PHASE-30.3 — Card de "Pagos a deuda" de Capa 1.
 *
 * Selector de rango (YTD / 12M / Mes), KPI grande con el total
 * y desglose intereses vs capital con una barra horizontal apilada
 * + tooltips educativos. Para usuarios sin datos en el rango,
 * pinta un mensaje "Sin pagos registrados".
 */
export function PaymentsSummaryCard({
  range,
  onRangeChange,
  totalPayments,
  interestsAndFees,
  capitalAmortized,
  currency,
  isLoading,
}: PaymentsSummaryCardProps) {
  const total = Number(totalPayments);
  const interests = Number(interestsAndFees);
  const interestPct = total > 0 ? Math.round((interests / total) * 100) : 0;
  const capitalPct = total > 0 ? 100 - interestPct : 0;
  const empty = !isLoading && total === 0;

  return (
    <Card
      style={{
        padding: spacing.lg,
        display: 'flex',
        flexDirection: 'column',
        gap: spacing.md,
      }}
    >
      <header
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: spacing.md,
          flexWrap: 'wrap',
        }}
      >
        <div>
          <h2
            style={{
              margin: 0,
              fontSize: fontSize.lg,
              fontWeight: fontWeight.semibold,
              color: colors.text,
              letterSpacing: '-0.01em',
            }}
          >
            {RANGE_TITLE[range]}
          </h2>
          <p
            style={{
              margin: `${spacing.xs}px 0 0 0`,
              fontSize: fontSize.xs,
              color: colors.textMuted,
              maxWidth: 480,
              lineHeight: 1.5,
            }}
          >
            Todo lo que has destinado a categorías marcadas como deuda
            (capital + intereses) en este periodo.
          </p>
        </div>
        <RangeSelector range={range} onChange={onRangeChange} />
      </header>

      {empty ? (
        <p
          style={{
            margin: 0,
            fontSize: fontSize.sm,
            color: colors.textMuted,
            backgroundColor: colors.surfaceMuted,
            borderRadius: radius.sm,
            padding: spacing.md,
            border: `1px dashed ${colors.border}`,
          }}
        >
          Sin pagos a deuda registrados en este periodo. Categoriza
          una transacción como deuda para empezar a ver el desglose.
        </p>
      ) : (
        <>
          <span
            style={{
              fontSize: fontSize.xxl,
              fontWeight: fontWeight.bold,
              color: colors.text,
              letterSpacing: '-0.02em',
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {isLoading ? '—' : formatAmount(totalPayments, currency)}
          </span>

          <div
            style={{
              display: 'flex',
              height: 14,
              width: '100%',
              borderRadius: 999,
              overflow: 'hidden',
              border: `1px solid ${colors.border}`,
              backgroundColor: colors.surfaceMuted,
            }}
            role="img"
            aria-label={`${capitalPct} por ciento capital, ${interestPct} por ciento intereses`}
          >
            <div
              style={{
                width: `${capitalPct}%`,
                backgroundColor: colors.primary,
              }}
            />
            <div
              style={{
                width: `${interestPct}%`,
                backgroundColor: colors.danger,
              }}
            />
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: spacing.md,
            }}
          >
            <Breakdown
              swatch={colors.primary}
              title="Capital amortizado"
              amount={formatAmount(capitalAmortized, currency)}
              pct={capitalPct}
              hint="Reduce tu deuda pendiente. Sale de tu bolsillo pero construye patrimonio."
            />
            <Breakdown
              swatch={colors.danger}
              title="Intereses y comisiones"
              amount={formatAmount(interestsAndFees, currency)}
              pct={interestPct}
              hint="El coste real de tu deuda. Dinero que no recuperas."
            />
          </div>
        </>
      )}
    </Card>
  );
}

function RangeSelector({
  range,
  onChange,
}: {
  range: DebtTimeRange;
  onChange: (range: DebtTimeRange) => void;
}) {
  const options: DebtTimeRange[] = ['ytd', '12m', 'month'];
  return (
    <div
      role="tablist"
      aria-label="Rango temporal"
      style={{
        display: 'inline-flex',
        padding: 2,
        backgroundColor: colors.surfaceMuted,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.sm,
        fontSize: fontSize.xs,
        fontWeight: fontWeight.semibold,
      }}
    >
      {options.map((opt) => {
        const active = opt === range;
        return (
          <button
            type="button"
            key={opt}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(opt)}
            style={{
              padding: `${spacing.xs}px ${spacing.sm}px`,
              backgroundColor: active ? colors.surface : 'transparent',
              color: active ? colors.text : colors.textMuted,
              border: 'none',
              borderRadius: radius.sm,
              cursor: 'pointer',
              boxShadow: active ? '0 1px 2px rgba(0,0,0,0.08)' : 'none',
            }}
          >
            {RANGE_LABEL[opt]}
          </button>
        );
      })}
    </div>
  );
}

function Breakdown({
  swatch,
  title,
  amount,
  pct,
  hint,
}: {
  swatch: string;
  title: string;
  amount: string;
  pct: number;
  hint: string;
}) {
  return (
    <div
      title={hint}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
        padding: spacing.sm,
        borderRadius: radius.sm,
        border: `1px solid ${colors.border}`,
        backgroundColor: colors.surface,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: spacing.xs,
          fontSize: fontSize.xs,
          color: colors.textMuted,
          fontWeight: fontWeight.medium,
          letterSpacing: '0.02em',
        }}
      >
        <span
          aria-hidden
          style={{
            width: 8,
            height: 8,
            borderRadius: 999,
            backgroundColor: swatch,
          }}
        />
        {title}
      </div>
      <div
        style={{
          fontSize: fontSize.md,
          fontWeight: fontWeight.semibold,
          color: colors.text,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {amount}{' '}
        <span
          style={{
            fontSize: fontSize.xs,
            color: colors.textMuted,
            fontWeight: fontWeight.regular,
          }}
        >
          · {pct}%
        </span>
      </div>
    </div>
  );
}
