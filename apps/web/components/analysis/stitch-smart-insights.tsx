'use client';

import type { CategoryBreakdownItem, DashboardSummary } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

import { Card } from '@/components/ui/card';
import {
  CheckCircleIcon,
  ChevronRightIcon,
  InfoIcon,
  SparklesIcon,
} from '@/components/ui/icons';

export interface StitchSmartInsightsProps {
  summary: DashboardSummary | undefined;
  expensesByCategory: CategoryBreakdownItem[] | undefined;
  currency: string;
}

interface Insight {
  kind: 'info' | 'success';
  title: string;
  body: string;
}

/**
 * Tarjetas de insights calculados client-side a partir de los datos
 * reales del usuario. Sin mocks: si no hay datos suficientes, sólo se
 * muestra el placeholder de "Gastos fijos recurrentes" (próximamente).
 */
export function StitchSmartInsights({
  summary,
  expensesByCategory,
  currency,
}: StitchSmartInsightsProps) {
  const insights = computeInsights(summary, expensesByCategory ?? [], currency);

  return (
    <Card
      style={{
        padding: spacing.lg,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div
        aria-hidden
        style={{
          position: 'absolute',
          right: -40,
          bottom: -40,
          opacity: 0.05,
          color: colors.primary,
          pointerEvents: 'none',
        }}
      >
        <SparklesIcon size={240} />
      </div>
      <h3
        style={{
          margin: 0,
          marginBottom: spacing.lg,
          fontSize: fontSize.lg,
          fontWeight: fontWeight.semibold,
          color: colors.text,
        }}
      >
        Smart Insights
      </h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
        {insights.length === 0 ? (
          <p style={{ margin: 0, fontSize: fontSize.sm, color: colors.textMuted }}>
            Todavía no hay datos suficientes para sacar insights. Sigue
            registrando transacciones y vuelve aquí.
          </p>
        ) : (
          insights.map((ins, idx) => (
            <InsightCard key={idx} insight={ins} />
          ))
        )}
        <ComingSoonRow
          title="Gastos fijos recurrentes"
          subtitle="Detección automática de cargos periódicos."
        />
      </div>
    </Card>
  );
}

function computeInsights(
  summary: DashboardSummary | undefined,
  byCategory: CategoryBreakdownItem[],
  currency: string,
): Insight[] {
  const out: Insight[] = [];
  if (!summary) return out;

  // 1) Saving rate / cash flow vs periodo anterior.
  const balance = Number(summary.balance);
  const previousBalance =
    summary.previous_period_balance != null ? Number(summary.previous_period_balance) : null;
  if (previousBalance !== null && balance > previousBalance && balance > 0) {
    out.push({
      kind: 'success',
      title: 'Mejor que el periodo anterior',
      body: `Tu saldo neto es ${currencyDelta(balance, previousBalance, currency)} mayor que el periodo anterior. Buena tendencia.`,
    });
  } else if (previousBalance !== null && balance < previousBalance) {
    out.push({
      kind: 'info',
      title: 'Bajada vs el periodo anterior',
      body: `Tu saldo neto bajó ${currencyDelta(previousBalance, balance, currency)} respecto al periodo previo. Revisa los gastos que más han crecido.`,
    });
  }

  // 2) Top categoría de gasto representando una porción importante.
  const expenses = Number(summary.expenses);
  if (expenses > 0 && byCategory.length > 0) {
    const top = [...byCategory].sort((a, b) => Number(b.total) - Number(a.total))[0];
    if (top) {
      const topVal = Number(top.total);
      const ratio = (topVal / expenses) * 100;
      if (ratio >= 30) {
        out.push({
          kind: 'info',
          title: `${top.category_name} concentra el ${ratio.toFixed(0)}% de tus gastos`,
          body: `Es la categoría con más peso del periodo. Revisa si puedes optimizarla con presupuestos por subcategoría.`,
        });
      }
    }
  }

  // 3) Tasa de ahorro saludable.
  const incomeNum = Number(summary.income);
  if (incomeNum > 0 && balance > 0) {
    const rate = (balance / incomeNum) * 100;
    if (rate >= 25) {
      out.push({
        kind: 'success',
        title: `Tasa de ahorro: ${rate.toFixed(0)}%`,
        body: `Estás ahorrando una proporción saludable de tus ingresos. El umbral recomendado es 20%.`,
      });
    }
  }

  return out;
}

function currencyDelta(a: number, b: number, currency: string): string {
  return `${(a - b).toFixed(2)} ${currency}`;
}

function InsightCard({ insight }: { insight: Insight }) {
  const { kind, title, body } = insight;
  const palette =
    kind === 'success'
      ? { bg: colors.successSoft, fg: colors.success }
      : { bg: colors.primarySoft, fg: colors.primary };
  const Icon = kind === 'success' ? CheckCircleIcon : InfoIcon;

  return (
    <div
      style={{
        backgroundColor: palette.bg,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.md,
        padding: spacing.md,
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm, color: palette.fg }}>
        <Icon size={18} />
        <span
          style={{
            fontSize: fontSize.sm,
            fontWeight: fontWeight.semibold,
            color: palette.fg,
          }}
        >
          {title}
        </span>
      </div>
      <p style={{ margin: 0, fontSize: fontSize.sm, color: colors.text, lineHeight: 1.5 }}>
        {body}
      </p>
    </div>
  );
}

function ComingSoonRow({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div
      style={{
        border: `1px dashed ${colors.borderStrong}`,
        borderRadius: radius.md,
        padding: spacing.md,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: spacing.sm,
      }}
    >
      <div>
        <span
          style={{
            display: 'block',
            fontSize: fontSize.sm,
            fontWeight: fontWeight.semibold,
            color: colors.text,
          }}
        >
          {title}
        </span>
        <span style={{ fontSize: fontSize.xs, color: colors.textSubtle }}>{subtitle}</span>
      </div>
      <span style={{ color: colors.textSubtle }}>
        <ChevronRightIcon size={18} />
      </span>
    </div>
  );
}
