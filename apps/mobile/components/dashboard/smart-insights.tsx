import { StyleSheet, Text, View } from 'react-native';

import type {
  CategoryBreakdownItem,
  DashboardSummary,
  ExpenseStructureResponse,
  MonthOutlookResponse,
} from '@crisol/types';
import { colors, fontSize, fontWeight, formatAmount, radius, spacing } from '@crisol/ui';

export interface SmartInsightsProps {
  summary: DashboardSummary | undefined;
  expensesByCategory: CategoryBreakdownItem[] | undefined;
  /** PHASE-37.6 (parity 37.3) — para el insight de impacto de puntuales. */
  structure: ExpenseStructureResponse | undefined;
  /** PHASE-37.6 (parity 37.4) — para el insight de cargo próximo. */
  outlook: MonthOutlookResponse | undefined;
  currency: string;
}

interface Insight {
  kind: 'info' | 'success';
  title: string;
  body: string;
  priority: number;
}

/**
 * PHASE-37.6 (parity 37.5) — Insights v2. MISMA lógica que
 * `StitchSmartInsights` (web): no-redundancia (fuera "saldo neto vs anterior"
 * y "tasa de ahorro", ya visibles en los KPIs) + generadores derivados
 * (concentración de gasto, impacto de puntuales de 37.3, cargo próximo de
 * 37.4). Máximo 3, por prioridad. Si diverge, extraer a `@crisol/services`.
 */
export function SmartInsights({
  summary,
  expensesByCategory,
  structure,
  outlook,
  currency,
}: SmartInsightsProps) {
  const insights = computeInsights(summary, expensesByCategory ?? [], structure, outlook, currency);

  return (
    <View style={styles.card}>
      <Text style={styles.heading}>Smart Insights</Text>
      {insights.length === 0 ? (
        <Text style={styles.empty}>
          Detección automática activa. Aún no hay una señal que no veas ya en los
          indicadores de arriba — cuando la haya, aparecerá aquí.
        </Text>
      ) : (
        insights.map((ins, idx) => <InsightRow key={idx} insight={ins} />)
      )}
    </View>
  );
}

function computeInsights(
  summary: DashboardSummary | undefined,
  byCategory: CategoryBreakdownItem[],
  structure: ExpenseStructureResponse | undefined,
  outlook: MonthOutlookResponse | undefined,
  currency: string,
): Insight[] {
  const out: Insight[] = [];

  // P1 — Concentración de gasto: una sola categoría domina el periodo.
  if (summary) {
    const expenses = Number(summary.expenses);
    const top = [...byCategory].sort((a, b) => Number(b.total) - Number(a.total))[0];
    if (expenses > 0 && top) {
      const ratio = (Number(top.total) / expenses) * 100;
      if (ratio >= 35) {
        out.push({
          kind: 'info',
          priority: 1,
          title: `${top.category_name} concentra el ${ratio.toFixed(0)}% de tus gastos`,
          body: 'Una sola categoría se lleva más de un tercio del gasto del periodo. Si es puntual, márcala como gasto puntual; si es estructural, un presupuesto ayuda a contenerla.',
        });
      }
    }
  }

  // P2 — Impacto de gastos puntuales (37.3): one-offs te dejan en negativo pero
  // el coste estructural está sano.
  if (
    structure &&
    structure.savings_rate_gross !== null &&
    structure.savings_rate_structural !== null &&
    structure.savings_rate_gross < 0 &&
    structure.savings_rate_structural > 0
  ) {
    const struct = structure.savings_rate_structural * 100;
    const gross = structure.savings_rate_gross * 100;
    out.push({
      kind: 'info',
      priority: 2,
      title: 'Los gastos puntuales marcan el periodo',
      body: `Sin los gastos puntuales (impuestos, one-offs) tu tasa de ahorro sería +${struct.toFixed(0)}% en vez de ${gross.toFixed(0)}%. Tu coste estructural está bajo control.`,
    });
  }

  // P3 — Cargo próximo relevante (37.4): el mayor cargo de los próximos 7 días
  // si domina lo comprometido.
  if (outlook) {
    const committed = Number(outlook.committed_remaining);
    const soon = upcomingWithin7Days(outlook.committed_items);
    const biggest = soon.sort((a, b) => Number(b.amount) - Number(a.amount))[0];
    if (biggest && committed > 0 && Number(biggest.amount) >= committed * 0.25) {
      out.push({
        kind: 'info',
        priority: 3,
        title: `Cargo próximo: ${biggest.name}`,
        body: `El ${formatDay(biggest.expected_date)} te llega ${formatAmount(biggest.amount, currency)}, el mayor cargo de los próximos días. Asegúrate de tener saldo.`,
      });
    }
  }

  return out.sort((a, b) => a.priority - b.priority).slice(0, 3);
}

function upcomingWithin7Days(items: MonthOutlookResponse['committed_items']) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const in7 = new Date(today);
  in7.setDate(in7.getDate() + 7);
  return items.filter((it) => {
    const d = new Date(`${it.expected_date}T00:00:00`);
    return d >= today && d <= in7;
  });
}

function formatDay(dateStr: string): string {
  return `${dateStr.slice(8, 10)}/${dateStr.slice(5, 7)}`;
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
});
