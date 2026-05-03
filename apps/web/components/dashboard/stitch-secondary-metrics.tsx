'use client';

import type { CategoryBreakdownItem, DashboardSummary } from '@finanzas/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';
import { formatAmount } from '@finanzas/ui';

import { Card } from '@/components/ui/card';
import { AlertTriangleIcon, RocketIcon } from '@/components/ui/icons';

export interface StitchSecondaryMetricsProps {
  summary: DashboardSummary | undefined;
  expensesByCategory: CategoryBreakdownItem[] | undefined;
  currency: string;
}

/**
 * Dos cards secundarias bajo la gráfica:
 * - "Mayor gasto" identifica la categoría con más gasto del periodo.
 *   Se llamó "Presupuesto en riesgo" en Stitch, pero como aún no
 *   tenemos modelo de presupuestos, lo etiquetamos como mayor gasto.
 * - "Ahorro proyectado": calcula `balance` y proyecta el final del
 *   mes asumiendo el mismo ritmo. Sólo se muestra cuando hay datos.
 */
export function StitchSecondaryMetrics({
  summary,
  expensesByCategory,
  currency,
}: StitchSecondaryMetricsProps) {
  const topCategory = pickTopCategory(expensesByCategory ?? []);
  const balance = summary ? Number(summary.balance) : 0;
  const projection = projectMonthlySaving(balance);

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: spacing.md,
      }}
    >
      <Card
        style={{
          padding: spacing.md,
          display: 'flex',
          alignItems: 'center',
          gap: spacing.md,
        }}
      >
        <CircleIcon background={colors.warningSoft} foreground={colors.warning}>
          <AlertTriangleIcon size={20} />
        </CircleIcon>
        <div style={{ minWidth: 0 }}>
          <span
            style={{
              fontSize: fontSize.xs,
              fontWeight: fontWeight.medium,
              color: colors.textMuted,
              display: 'block',
            }}
          >
            Mayor gasto del periodo
          </span>
          <span
            style={{
              fontSize: fontSize.md,
              fontWeight: fontWeight.semibold,
              color: colors.text,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              display: 'inline-block',
            }}
          >
            {topCategory
              ? `${topCategory.name} · ${formatAmount(topCategory.total, currency)}`
              : 'Sin gastos en el periodo'}
          </span>
        </div>
      </Card>

      <Card
        style={{
          padding: spacing.md,
          display: 'flex',
          alignItems: 'center',
          gap: spacing.md,
        }}
      >
        <CircleIcon background={colors.primarySoft} foreground={colors.primary}>
          <RocketIcon size={20} />
        </CircleIcon>
        <div style={{ minWidth: 0 }}>
          <span
            style={{
              fontSize: fontSize.xs,
              fontWeight: fontWeight.medium,
              color: colors.textMuted,
              display: 'block',
            }}
          >
            Ahorro proyectado
          </span>
          <span
            style={{
              fontSize: fontSize.md,
              fontWeight: fontWeight.semibold,
              color: projection.value >= 0 ? colors.text : colors.danger,
              whiteSpace: 'nowrap',
            }}
          >
            {projection.label
              ? `${formatAmount(String(projection.value.toFixed(2)), currency)} ${projection.label}`
              : 'Sin datos para proyectar'}
          </span>
        </div>
      </Card>
    </div>
  );
}

function pickTopCategory(items: CategoryBreakdownItem[]): { name: string; total: string } | null {
  const sorted = [...items].sort((a, b) => Number(b.total) - Number(a.total));
  const top = sorted[0];
  if (!top || Number(top.total) === 0) return null;
  return { name: top.category_name, total: top.total };
}

function projectMonthlySaving(balanceSoFar: number): { value: number; label: string | null } {
  if (balanceSoFar === 0) return { value: 0, label: null };
  // Proyección lineal naïve: extrapolamos el balance actual al fin de mes.
  const now = new Date();
  const dayOfMonth = now.getDate();
  const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
  if (dayOfMonth === 0) return { value: 0, label: null };
  const projected = (balanceSoFar / dayOfMonth) * daysInMonth;
  return { value: projected, label: balanceSoFar >= 0 ? 'a fin de mes' : 'a fin de mes' };
}

function CircleIcon({
  background,
  foreground,
  children,
}: {
  background: string;
  foreground: string;
  children: React.ReactNode;
}) {
  return (
    <div
      aria-hidden
      style={{
        width: 40,
        height: 40,
        borderRadius: '50%',
        backgroundColor: background,
        color: foreground,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        flex: '0 0 auto',
        ...{ '--unused': '0' },
      } as React.CSSProperties}
    >
      <div style={{ borderRadius: radius.sm }}>{children}</div>
    </div>
  );
}
