'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';

import {
  periodLabel,
  useAccountBalances,
  useDebtCategorySummary,
  useDebtHealth,
  useDebtHistory,
} from '@crisol/services';
import { useCurrencyStore } from '@crisol/store';
import type { DebtTimeRange } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

import { DebtCompositionDonut } from '@/components/debt/debt-composition-donut';
import { DebtList } from '@/components/debt/debt-list';
import { DebtMonthlyEvolution } from '@/components/debt/debt-monthly-evolution';
import { DebtTrendChart } from '@/components/debt/debt-trend-chart';
import { EffortRatioSection } from '@/components/debt/effort-ratio-section';
import { PaymentsSummaryCard } from '@/components/debt/payments-summary-card';
import { PeriodNavigator } from '@/components/debt/period-navigator';
import { RecurringQuotasList } from '@/components/debt/recurring-quotas-list';
import { ErrorState } from '@/components/ui/error-state';

/**
 * Página `/debt` rediseñada en PHASE-30.3.
 *
 * Capa 1 (flujo de categorías) primero, sin requerir liability
 * accounts: tasa de esfuerzo, pagos a deuda en el rango, composición
 * por tipo, evolución mensual y cuotas recurrentes detectadas.
 *
 * Capa 2 (contratos concretos) abajo: lista de liabilities con sus
 * cuotas + chart de evolución del saldo. Empty state pide vincular
 * cuando hay cuotas recurrentes pero ningún liability declarado.
 */
export default function DebtPage() {
  const [range, setRange] = useState<DebtTimeRange>('year');
  // PHASE-30.8 — Mes ancla `YYYY-MM` del período mostrado. Por defecto
  // el mes en curso → período actual (comportamiento previo). El
  // `PeriodNavigator` lo mueve (limitado a los meses con datos).
  const [anchorMonth, setAnchorMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  });
  // PHASE-30.6 — el selector global de divisa del header pasa por aquí
  // como `target_currency` a los tres endpoints de deuda. Sin `convertAll`
  // (modo legacy del dashboard) volvemos al comportamiento native:
  // moneda de referencia de la primera cuenta del usuario.
  const storeCurrency = useCurrencyStore((s) => s.currency);
  const convertAll = useCurrencyStore((s) => s.convertAll);
  const targetCurrency = convertAll ? storeCurrency : undefined;

  const summaryQuery = useDebtCategorySummary(range, {
    anchor: `${anchorMonth}-01`,
    ...(targetCurrency ? { targetCurrency } : {}),
  });
  const healthQuery = useDebtHealth(
    targetCurrency ? { targetCurrency } : {},
  );
  const balancesQuery = useAccountBalances();
  const historyQuery = useDebtHistory({
    monthsBack: 12,
    monthsAhead: 12,
    ...(targetCurrency ? { targetCurrency } : {}),
  });

  const liabilities = useMemo(
    () =>
      (balancesQuery.data?.items ?? []).filter(
        (item) => item.nature === 'liability',
      ),
    [balancesQuery.data],
  );

  const summary = summaryQuery.data;
  const health = healthQuery.data;

  const referenceCurrency =
    summary?.reference_currency ??
    health?.reference_currency ??
    historyQuery.data?.reference_currency ??
    balancesQuery.data?.reference_currency ??
    'EUR';

  // PHASE-30.8 — Numerador (pagos a deuda) y denominador (ingreso) del
  // período, ambos del category-summary, para que el gauge y las cifras
  // sean coherentes con el período elegido. El numerador ampliado se
  // deriva del ratio ampliado (el backend no expone su absoluto).
  const monthlyIncome = summary?.monthly_income_avg ?? '0';
  const monthlyDebtPayment = summary?.monthly_debt_payment_avg ?? '0';
  const monthlyDebtPaymentExtended =
    summary && summary.effort_ratio_extended !== null
      ? (
          summary.effort_ratio_extended * Number(monthlyIncome)
        ).toFixed(2)
      : monthlyDebtPayment;

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: spacing.lg }}>
      <PageHeader />

      <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
        <PeriodNavigator
          range={range}
          onRangeChange={setRange}
          anchor={anchorMonth}
          onAnchorChange={setAnchorMonth}
          availableFrom={summary?.available_from ?? null}
          availableTo={summary?.available_to ?? null}
        />
        {summaryQuery.isError ? (
          <ErrorState
            description="No se pudieron cargar tus métricas de deuda. Las cifras de abajo pueden estar incompletas."
            onRetry={() => void summaryQuery.refetch()}
            retrying={summaryQuery.isFetching}
            compact
          />
        ) : null}
        <EffortRatioSection
          strictRatio={summary?.effort_ratio_strict ?? null}
          strictStatus={summary?.effort_ratio_strict_status ?? 'unknown'}
          extendedRatio={summary?.effort_ratio_extended ?? null}
          extendedStatus={summary?.effort_ratio_extended_status ?? 'unknown'}
          monthlyIncome={monthlyIncome}
          monthlyDebtPayment={monthlyDebtPayment}
          monthlyDebtPaymentExtended={monthlyDebtPaymentExtended}
          currency={referenceCurrency}
          isLoading={summaryQuery.isLoading}
        />

        <PaymentsSummaryCard
          title={`Pagos a deuda — ${periodLabel(range, anchorMonth)}`}
          totalPayments={summary?.total_payments ?? '0'}
          interestsAndFees={summary?.interests_and_fees ?? '0'}
          capitalAmortized={summary?.capital_amortized ?? '0'}
          currency={referenceCurrency}
          isLoading={summaryQuery.isLoading}
        />

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(280px, 1fr) minmax(360px, 1.6fr)',
            gap: spacing.md,
          }}
        >
          <DebtCompositionDonut
            items={summary?.by_type ?? []}
            total={summary?.total_payments ?? '0'}
            currency={referenceCurrency}
            isLoading={summaryQuery.isLoading}
          />
          <DebtMonthlyEvolution
            items={summary?.monthly_series ?? []}
            currency={referenceCurrency}
            isLoading={summaryQuery.isLoading}
          />
        </div>

        <RecurringQuotasList
          items={summary?.recurring_quotas ?? []}
          currency={referenceCurrency}
          isLoading={summaryQuery.isLoading}
        />

        <Layer2Section
          hasLiabilities={liabilities.length > 0}
          hasRecurringQuotas={(summary?.recurring_quotas.length ?? 0) > 0}
        >
          {historyQuery.data && historyQuery.data.items.length > 0 ? (
            <DebtTrendChart
              data={historyQuery.data.items}
              currency={referenceCurrency}
              isLoading={historyQuery.isLoading}
            />
          ) : null}
          <DebtList
            liabilities={liabilities}
            loading={balancesQuery.isLoading}
          />
        </Layer2Section>
      </div>
    </div>
  );
}

function PageHeader() {
  return (
    <header
      style={{
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'space-between',
        gap: spacing.md,
        flexWrap: 'wrap',
        marginBottom: spacing.xl,
      }}
    >
      <div>
        <span
          style={{
            fontSize: 11,
            fontWeight: fontWeight.semibold,
            color: colors.primary,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            display: 'block',
            marginBottom: spacing.xs,
          }}
        >
          DEUDA
        </span>
        <h1
          style={{
            margin: 0,
            fontSize: fontSize.xxl,
            fontWeight: fontWeight.bold,
            color: colors.text,
            letterSpacing: '-0.02em',
            lineHeight: 1.1,
          }}
        >
          Deuda
        </h1>
        <p
          style={{
            margin: `${spacing.xs}px 0 0 0`,
            color: colors.textMuted,
            fontSize: fontSize.sm,
            maxWidth: 640,
            lineHeight: 1.5,
          }}
        >
          Tu salud financiera de un vistazo: cuánto destinas a deuda
          frente a tus ingresos, qué proporción es interés puro y
          cómo evoluciona mes a mes.
        </p>
      </div>
      <Link
        href="/settings/accounts"
        style={{
          display: 'inline-block',
          padding: `${spacing.sm}px ${spacing.md}px`,
          borderRadius: radius.md,
          backgroundColor: colors.primary,
          color: colors.onPrimary,
          fontSize: fontSize.sm,
          fontWeight: fontWeight.semibold,
          textDecoration: 'none',
          border: `1px solid ${colors.primary}`,
        }}
      >
        Añadir deuda
      </Link>
    </header>
  );
}

function Layer2Section({
  hasLiabilities,
  hasRecurringQuotas,
  children,
}: {
  hasLiabilities: boolean;
  hasRecurringQuotas: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(hasLiabilities);

  return (
    <section
      style={{
        backgroundColor: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.md,
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        style={{
          width: '100%',
          background: 'transparent',
          border: 'none',
          padding: `${spacing.md}px ${spacing.lg}px`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          cursor: 'pointer',
          textAlign: 'left',
        }}
        aria-expanded={open}
      >
        <span>
          <span
            style={{
              fontSize: fontSize.md,
              fontWeight: fontWeight.semibold,
              color: colors.text,
              letterSpacing: '-0.01em',
            }}
          >
            Detalle por contrato
          </span>
          <span
            style={{
              display: 'block',
              fontSize: fontSize.xs,
              color: colors.textMuted,
              marginTop: 2,
            }}
          >
            {hasLiabilities
              ? 'Tus pasivos declarados con sus cuotas y cuadros de amortización.'
              : hasRecurringQuotas
                ? 'Cuotas detectadas pero sin contrato vinculado — añade uno para que cuenten en tu patrimonio.'
                : 'Vacío. Añade un préstamo / hipoteca / tarjeta cuando tengas un contrato real.'}
          </span>
        </span>
        <span
          aria-hidden
          style={{
            fontSize: fontSize.lg,
            color: colors.textMuted,
            transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 120ms ease',
          }}
        >
          ▾
        </span>
      </button>

      {open ? (
        <div
          style={{
            padding: `0 ${spacing.lg}px ${spacing.lg}px`,
            display: 'flex',
            flexDirection: 'column',
            gap: spacing.md,
          }}
        >
          {children}
        </div>
      ) : null}
    </section>
  );
}
