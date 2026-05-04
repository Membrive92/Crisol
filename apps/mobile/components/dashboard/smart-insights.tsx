import { StyleSheet, Text, View } from 'react-native';

import type { CategoryBreakdownItem, DashboardSummary } from '@finanzas/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

export interface SmartInsightsProps {
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
 * Insights computados client-side a partir de `summary` +
 * `expensesByCategory`. Mismo cómputo que `StitchSmartInsights` (web)
 * — si no hay datos suficientes muestra mensaje neutro.
 */
export function SmartInsights({ summary, expensesByCategory, currency }: SmartInsightsProps) {
  const insights = computeInsights(summary, expensesByCategory ?? [], currency);

  return (
    <View style={styles.card}>
      <Text style={styles.heading}>Smart Insights</Text>
      {insights.length === 0 ? (
        <Text style={styles.empty}>
          Todavía no hay datos suficientes para sacar insights. Sigue registrando
          transacciones y vuelve aquí.
        </Text>
      ) : (
        insights.map((ins, idx) => <InsightRow key={idx} insight={ins} />)
      )}
      <View style={styles.comingSoon}>
        <View style={{ flex: 1 }}>
          <Text style={styles.comingSoonTitle}>Subscripciones recurrentes</Text>
          <Text style={styles.comingSoonSubtitle}>
            Detección automática de cargos periódicos.
          </Text>
        </View>
      </View>
    </View>
  );
}

function computeInsights(
  summary: DashboardSummary | undefined,
  byCategory: CategoryBreakdownItem[],
  currency: string,
): Insight[] {
  const out: Insight[] = [];
  if (!summary) return out;

  const balance = Number(summary.balance);
  const previousBalance =
    summary.previous_period_balance != null ? Number(summary.previous_period_balance) : null;

  if (previousBalance !== null && balance > previousBalance && balance > 0) {
    out.push({
      kind: 'success',
      title: 'Mejor que el periodo anterior',
      body: `Tu saldo neto es ${(balance - previousBalance).toFixed(2)} ${currency} mayor que el periodo anterior. Buena tendencia.`,
    });
  } else if (previousBalance !== null && balance < previousBalance) {
    out.push({
      kind: 'info',
      title: 'Bajada vs el periodo anterior',
      body: `Tu saldo neto bajó ${(previousBalance - balance).toFixed(2)} ${currency} respecto al periodo previo. Revisa los gastos que más han crecido.`,
    });
  }

  const expenses = Number(summary.expenses);
  if (expenses > 0 && byCategory.length > 0) {
    const top = [...byCategory].sort((a, b) => Number(b.total) - Number(a.total))[0];
    if (top) {
      const ratio = (Number(top.total) / expenses) * 100;
      if (ratio >= 30) {
        out.push({
          kind: 'info',
          title: `${top.category_name} concentra el ${ratio.toFixed(0)}% de tus gastos`,
          body: 'Es la categoría con más peso del periodo. Revisa si puedes optimizarla con presupuestos por subcategoría.',
        });
      }
    }
  }

  const income = Number(summary.income);
  if (income > 0 && balance > 0) {
    const rate = (balance / income) * 100;
    if (rate >= 25) {
      out.push({
        kind: 'success',
        title: `Tasa de ahorro: ${rate.toFixed(0)}%`,
        body: 'Estás ahorrando una proporción saludable de tus ingresos. El umbral recomendado es 20%.',
      });
    }
  }

  return out;
}

function InsightRow({ insight }: { insight: Insight }) {
  const palette =
    insight.kind === 'success'
      ? { bg: colors.successSoft, fg: colors.success }
      : { bg: colors.primarySoft, fg: colors.primary };

  return (
    <View style={[styles.insight, { backgroundColor: palette.bg }]}>
      <Text style={[styles.insightTitle, { color: palette.fg }]}>{insight.title}</Text>
      <Text style={styles.insightBody}>{insight.body}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
    gap: spacing.sm,
  },
  heading: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
    marginBottom: spacing.xs,
  },
  empty: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    lineHeight: 20,
  },
  insight: {
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    gap: 4,
  },
  insightTitle: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
  },
  insightBody: {
    fontSize: fontSize.sm,
    color: colors.text,
    lineHeight: 20,
  },
  comingSoon: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    borderStyle: 'dashed',
    padding: spacing.md,
  },
  comingSoonTitle: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  comingSoonSubtitle: {
    fontSize: fontSize.xs,
    color: colors.textSubtle,
    marginTop: 2,
  },
});
