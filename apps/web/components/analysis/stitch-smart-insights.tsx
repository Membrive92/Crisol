'use client';

import type {
  CategoryBreakdownItem,
  DashboardSummary,
  ExpenseStructureResponse,
} from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

import { Card } from '@/components/ui/card';
import { CheckCircleIcon, InfoIcon, SparklesIcon } from '@/components/ui/icons';

export interface StitchSmartInsightsProps {
  summary: DashboardSummary | undefined;
  expensesByCategory: CategoryBreakdownItem[] | undefined;
  /** PHASE-37.5 — gasto estructural/puntual (37.3), para el insight de impacto de puntuales. */
  structure: ExpenseStructureResponse | undefined;
}

interface Insight {
  kind: 'info' | 'success';
  title: string;
  body: string;
  /** Prioridad (1 = más importante). Se ordena por ella y se topan a 3. */
  priority: number;
}

/**
 * PHASE-37.5 — Insights v2, calculados client-side. Regla de NO-REDUNDANCIA:
 * no se emite un insight cuyo dato principal ya sea visible en un KPI/card del
 * layout. Por eso se ELIMINARON los insights de "saldo neto vs periodo
 * anterior" (duplicaba el Δ del tile Flujo) y "tasa de ahorro" (duplicaba el
 * tile T. Ahorro). PHASE-43.3 — retirado el insight prospectivo "cargo próximo"
 * (viaja al dashboard con el month-outlook: Análisis es sólo flujos). Máximo 3.
 */
export function StitchSmartInsights({
  summary,
  expensesByCategory,
  structure,
}: StitchSmartInsightsProps) {
  const insights = computeInsights(summary, expensesByCategory ?? [], structure);

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
            Detección automática activa. Aún no hay una señal que no veas ya en
            los indicadores de arriba — cuando la haya, aparecerá aquí.
          </p>
        ) : (
          insights.map((ins, idx) => <InsightCard key={idx} insight={ins} />)
        )}
      </div>
    </Card>
  );
}

/**
 * PHASE-37.5 — Genera los insights v2 y los topa a 3 por prioridad. Cada
 * generador comprueba antes que su dato NO sea ya visible en un KPI/card del
 * layout (no-redundancia). Exportada para testear la lógica sin renderizar.
 */
export function computeInsights(
  summary: DashboardSummary | undefined,
  byCategory: CategoryBreakdownItem[],
  structure: ExpenseStructureResponse | undefined,
): Insight[] {
  const out: Insight[] = [];

  // P1 — Concentración de gasto: una sola categoría domina el periodo. (El
  // donut muestra el reparto pero no señala la concentración como alerta.)
  if (summary) {
    // PHASE-47.E — el denominador se suma del PROPIO desglose, no de
    // `summary.expenses`. Desde que el resultado del mes excluye las compras
    // aplazadas y el desglose las mantiene, las dos cifras difieren a
    // propósito: dividir una por la otra da porcentajes imposibles (con
    // 609,14 € aplazados de 909,14 € de gasto, «Compras concentra el 220 % de
    // tus gastos»). Un ratio tiene que salir de un solo universo.
    const expenses = byCategory.reduce((acc, c) => acc + Number(c.total), 0);
    const top = [...byCategory].sort((a, b) => Number(b.total) - Number(a.total))[0];
    if (expenses > 0 && top) {
      const ratio = (Number(top.total) / expenses) * 100;
      if (ratio >= 35) {
        out.push({
          kind: 'info',
          priority: 1,
          title: `${top.category_name} concentra el ${ratio.toFixed(0)}% de tus gastos`,
          body: 'Una sola categoría se lleva más de un tercio del gasto del periodo. Si es variable, márcala como gasto variable; si es fija, un presupuesto ayuda a contenerla.',
        });
      }
    }
  }

  // P2 — Impacto de gastos puntuales (37.3): los one-offs te dejan en negativo
  // pero el coste estructural está sano. Enmarca el dato, no lo repite.
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
      title: 'Los gastos variables marcan el periodo',
      body: `Sin los gastos variables (impuestos, puntuales) tu tasa de ahorro sería +${struct.toFixed(0)}% en vez de ${gross.toFixed(0)}%. Tu coste fijo está bajo control.`,
    });
  }

  return out.sort((a, b) => a.priority - b.priority).slice(0, 3);
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

