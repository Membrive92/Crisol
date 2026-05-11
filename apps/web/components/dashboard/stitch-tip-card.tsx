'use client';

import type { DashboardSummary } from '@crisol/types';
import { colors, fontSize, fontWeight, spacing } from '@crisol/ui';
import { formatAmount } from '@crisol/ui';

import { Card } from '@/components/ui/card';
import { SparklesIcon } from '@/components/ui/icons';

export interface StitchTipCardProps {
  summary: DashboardSummary | undefined;
}

/**
 * Card de "Consejo financiero" estilo Stitch — bg `primary-soft`, eyebrow
 * + insight calculado client-side (delta vs periodo previo del balance).
 * Cuando no hay datos suficientes, cae a un consejo estático.
 */
export function StitchTipCard({ summary }: StitchTipCardProps) {
  const tip = pickTip(summary);

  return (
    <Card
      style={{
        backgroundColor: colors.primarySoft,
        border: `1px solid ${colors.border}`,
        padding: spacing.md,
        display: 'flex',
        flexDirection: 'column',
        gap: spacing.xs,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div
        aria-hidden
        style={{
          position: 'absolute',
          top: -20,
          right: -20,
          opacity: 0.08,
          color: colors.primary,
          pointerEvents: 'none',
        }}
      >
        <SparklesIcon size={120} />
      </div>
      <span
        style={{
          fontSize: 11,
          fontWeight: fontWeight.semibold,
          color: colors.primary,
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
        }}
      >
        Consejo financiero
      </span>
      <p
        style={{
          margin: 0,
          fontSize: fontSize.sm,
          color: colors.text,
          lineHeight: 1.5,
        }}
      >
        {tip.body}
      </p>
      <span style={{ fontSize: fontSize.xs, color: colors.textSubtle, marginTop: spacing.xs }}>
        {tip.cta}
      </span>
    </Card>
  );
}

function pickTip(summary: DashboardSummary | undefined): { body: string; cta: string } {
  if (!summary) {
    return {
      body: 'Sube tickets, importa CSVs o registra transacciones a mano para empezar a ver patrones.',
      cta: 'Tu IA local extrae los datos sin salir del equipo.',
    };
  }

  const balance = Number(summary.balance);
  const previous = summary.previous_period_balance != null ? Number(summary.previous_period_balance) : null;
  const income = Number(summary.income);
  const expenses = Number(summary.expenses);
  const currency = summary.currency;

  if (previous !== null && previous !== 0 && balance > previous) {
    const delta = ((balance - previous) / Math.abs(previous)) * 100;
    return {
      body: `Tu saldo neto es ${delta.toFixed(0)}% mejor que el periodo anterior. Buen ritmo.`,
      cta: 'Mantén el control con presupuestos por categoría (próximamente).',
    };
  }

  if (income > 0 && expenses > 0) {
    const ratio = (expenses / income) * 100;
    if (ratio < 70) {
      return {
        body: `Estás gastando el ${ratio.toFixed(0)}% de tus ingresos. Una tasa de ahorro saludable.`,
        cta: 'El umbral recomendado es <80%. Vas sobrado.',
      };
    }
    if (ratio > 95) {
      return {
        body: `Tus gastos suponen el ${ratio.toFixed(0)}% de tus ingresos este periodo.`,
        cta: 'Revisa el desglose por categoría para identificar dónde recortar.',
      };
    }
  }

  return {
    body: `Llevas ${formatAmount(summary.balance, currency)} de saldo neto en el periodo.`,
    cta: 'Sigue registrando transacciones para que la IA aprenda tus patrones.',
  };
}
