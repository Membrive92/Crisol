'use client';

import Link from 'next/link';
import { useMemo } from 'react';

import { useAccountBalances, useDebtHistory } from '@crisol/services';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

import { DebtHealthCard } from '@/components/dashboard/debt-health-card';
import { DebtList } from '@/components/debt/debt-list';
import { DebtTrendChart } from '@/components/debt/debt-trend-chart';

/**
 * Página de aterrizaje del módulo deuda (PHASE-22+, promocionado a
 * top-level).
 *
 * Concentra en una sola vista:
 * - Hero con `DebtHealthCard` (patrimonio neto + KPIs de salud).
 * - Chart de evolución histórico + proyección de la deuda total.
 * - Lista de pasivos activos con cuotas estimadas y enlaces a sus
 *   cuadros de amortización.
 *
 * La página es snapshot — no aplica el toggle de periodo del análisis
 * porque la deuda es un saldo, no un flujo. Las cuentas siguen
 * gestionándose desde Finanzas Domésticas (`/settings/accounts`).
 */
export default function DebtPage() {
  const balancesQuery = useAccountBalances();
  const historyQuery = useDebtHistory({ monthsBack: 12, monthsAhead: 12 });

  const liabilities = useMemo(
    () =>
      (balancesQuery.data?.items ?? []).filter(
        (item) => item.nature === 'liability',
      ),
    [balancesQuery.data],
  );

  const referenceCurrency =
    historyQuery.data?.reference_currency ??
    balancesQuery.data?.reference_currency ??
    'EUR';

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: spacing.lg }}>
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
            Patrimonio, salud financiera, evolución y cada pasivo con su
            cuota — todo el panorama de deuda sin saltar entre pantallas.
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

      <div style={{ marginBottom: spacing.md }}>
        <DebtHealthCard />
      </div>

      <div style={{ marginBottom: spacing.md }}>
        <DebtTrendChart
          data={historyQuery.data?.items ?? []}
          currency={referenceCurrency}
          isLoading={historyQuery.isLoading}
        />
      </div>

      <DebtList liabilities={liabilities} loading={balancesQuery.isLoading} />
    </div>
  );
}
