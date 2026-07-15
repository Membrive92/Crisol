'use client';

import type { ReactNode } from 'react';

import type { DashboardSummary } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';
import { formatAmount } from '@crisol/ui';

import { Card } from '@/components/ui/card';
import {
  BanknoteIcon,
  MoreHorizontalIcon,
  TrendingDownIcon,
  TrendingUpIcon,
  WalletIcon,
} from '@/components/ui/icons';

export interface StitchKpiRowProps {
  summary: DashboardSummary | undefined;
  isLoading: boolean;
  /** PHASE — Patrimonio neto (stock). `net_worth` o `total_assets` según el
   * toggle `includeDebtInNetWorth` del header. `null` mientras carga o sin datos. */
  netWorth?: string | null | undefined;
  includeDebt?: boolean | undefined;
  netWorthLoading?: boolean | undefined;
}

/**
 * Fila de KPIs del dashboard al estilo Stitch:
 * - Patrimonio neto (stock) — reacciona al toggle de deuda del header.
 * - Saldo Total (flujo del periodo) con delta vs periodo previo.
 * - Ingresos con badge "RECURRENTE" cuando hay transactions del periodo.
 * - Gastos con barra de presupuesto + caption de % gastado.
 */
export function StitchKpiRow({
  summary,
  isLoading,
  netWorth,
  includeDebt,
  netWorthLoading,
}: StitchKpiRowProps) {
  const currency = summary?.currency ?? 'EUR';
  const balance = summary ? Number(summary.balance) : 0;
  const balanceColor = balance >= 0 ? colors.text : colors.danger;
  const previousBalance =
    summary?.previous_period_balance != null
      ? Number(summary.previous_period_balance)
      : null;
  const balanceDelta =
    previousBalance !== null && previousBalance !== 0
      ? ((balance - previousBalance) / Math.abs(previousBalance)) * 100
      : null;

  const incomeNum = summary ? Number(summary.income) : 0;
  const expensesNum = summary ? Number(summary.expenses) : 0;
  const expenseRatio = incomeNum > 0 ? Math.min(1, expensesNum / incomeNum) : 0;

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: spacing.md,
      }}
    >
      {/* Patrimonio neto (stock) — reacciona al toggle de deuda del header. */}
      <Card style={{ display: 'flex', flexDirection: 'column', gap: spacing.xs, padding: spacing.md }}>
        <Header
          label="Patrimonio neto"
          trailing={<WalletIcon size={18} style={{ color: colors.textSubtle }} />}
        />
        <span
          style={{
            fontSize: fontSize.xxl,
            fontWeight: fontWeight.bold,
            color: colors.text,
            letterSpacing: '-0.01em',
            fontVariantNumeric: 'tabular-nums',
            lineHeight: 1.15,
          }}
        >
          {netWorth != null && !netWorthLoading ? formatAmount(netWorth, currency) : '—'}
        </span>
        <span style={{ fontSize: fontSize.xs, color: colors.textSubtle }}>
          {includeDebt ? 'Activos − deuda' : 'Solo activos'}
        </span>
      </Card>

      {/* Saldo Total */}
      <Card style={{ display: 'flex', flexDirection: 'column', gap: spacing.xs, padding: spacing.md }}>
        <Header
          label="Saldo Total"
          trailing={<BanknoteIcon size={18} style={{ color: colors.textSubtle }} />}
        />
        <span
          style={{
            fontSize: fontSize.xxl,
            fontWeight: fontWeight.bold,
            color: balanceColor,
            letterSpacing: '-0.01em',
            fontVariantNumeric: 'tabular-nums',
            lineHeight: 1.15,
          }}
        >
          {summary && !isLoading ? formatAmount(summary.balance, currency) : '—'}
        </span>
        <DeltaCaption pct={balanceDelta} />
      </Card>

      {/* Ingresos este mes */}
      <Card style={{ display: 'flex', flexDirection: 'column', gap: spacing.xs, padding: spacing.md }}>
        <Header
          label="Ingresos este periodo"
          trailing={
            summary && summary.transaction_count > 0 ? (
              <span
                style={{
                  fontSize: 10,
                  fontWeight: fontWeight.semibold,
                  color: colors.success,
                  backgroundColor: colors.successSoft,
                  padding: '2px 8px',
                  borderRadius: radius.sm,
                  letterSpacing: '0.04em',
                  textTransform: 'uppercase',
                }}
              >
                Recurrente
              </span>
            ) : null
          }
        />
        <span
          style={{
            fontSize: fontSize.xxl,
            fontWeight: fontWeight.bold,
            color: colors.success,
            letterSpacing: '-0.01em',
            fontVariantNumeric: 'tabular-nums',
            lineHeight: 1.15,
          }}
        >
          {summary && !isLoading ? formatAmount(summary.income, currency) : '—'}
        </span>
        <span style={{ fontSize: fontSize.xs, color: colors.textSubtle }}>
          {summary ? `${summary.transaction_count} transacciones` : '—'}
        </span>
      </Card>

      {/* Gastos este mes */}
      <Card style={{ display: 'flex', flexDirection: 'column', gap: spacing.xs, padding: spacing.md }}>
        <Header
          label="Gastos este periodo"
          trailing={
            <button
              type="button"
              aria-label="Más opciones"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 22,
                height: 22,
                background: 'transparent',
                border: 'none',
                color: colors.textSubtle,
                cursor: 'pointer',
              }}
            >
              <MoreHorizontalIcon size={16} />
            </button>
          }
        />
        <span
          style={{
            fontSize: fontSize.xxl,
            fontWeight: fontWeight.bold,
            color: colors.danger,
            letterSpacing: '-0.01em',
            fontVariantNumeric: 'tabular-nums',
            lineHeight: 1.15,
          }}
        >
          {summary && !isLoading ? formatAmount(summary.expenses, currency) : '—'}
        </span>
        <div
          style={{
            width: '100%',
            height: 4,
            backgroundColor: colors.surfaceMuted,
            borderRadius: 2,
            overflow: 'hidden',
            marginTop: 4,
          }}
        >
          <div
            style={{
              width: `${expenseRatio * 100}%`,
              height: '100%',
              backgroundColor: expenseRatio > 0.85 ? colors.danger : colors.warning,
              transition: 'width 200ms ease',
            }}
          />
        </div>
        <span style={{ fontSize: fontSize.xs, color: colors.textSubtle }}>
          {summary && incomeNum > 0
            ? `${(expenseRatio * 100).toFixed(0)}% de los ingresos`
            : 'Sin ingresos en el periodo'}
        </span>
      </Card>
    </div>
  );
}

function Header({ label, trailing }: { label: string; trailing: ReactNode }) {
  return (
    <header
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: spacing.sm,
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
      {trailing}
    </header>
  );
}

function DeltaCaption({ pct }: { pct: number | null }) {
  if (pct === null) {
    return (
      <span style={{ fontSize: fontSize.xs, color: colors.textSubtle }}>
        Sin periodo previo para comparar
      </span>
    );
  }
  const isUp = pct > 0;
  const color = isUp ? colors.success : pct < 0 ? colors.danger : colors.textSubtle;
  const Arrow = isUp ? TrendingUpIcon : TrendingDownIcon;
  const sign = isUp ? '+' : '';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: spacing.xs, marginTop: 2 }}>
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 2,
          color,
          fontSize: 11,
          fontWeight: fontWeight.semibold,
          letterSpacing: '0.02em',
          textTransform: 'uppercase',
        }}
      >
        <Arrow size={12} />
        {sign}
        {pct.toFixed(1)}%
      </span>
      <span style={{ fontSize: fontSize.xs, color: colors.textSubtle }}>
        vs periodo anterior
      </span>
    </div>
  );
}
