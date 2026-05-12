import { StyleSheet, Text, View } from 'react-native';

import { useDebtHealth } from '@crisol/services';
import type { DtiStatus } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
} from '@crisol/ui';

/**
 * Mapea el estado del ratio DTI a un par fondo + texto coherente con
 * la paleta semántica existente.
 */
function dtiStatusColors(status: DtiStatus): {
  bg: string;
  fg: string;
  label: string;
} {
  switch (status) {
    case 'healthy':
      return { bg: colors.successSoft, fg: colors.success, label: 'Saludable' };
    case 'caution':
      return { bg: colors.warningSoft, fg: colors.warning, label: 'Atención' };
    case 'stressed':
      return { bg: colors.dangerSoft, fg: colors.danger, label: 'Estresado' };
    case 'unknown':
    default:
      return { bg: colors.surfaceMuted, fg: colors.textMuted, label: 'Sin datos' };
  }
}

/**
 * Formatea un número de meses en "X años Y meses" (los <12 quedan como
 * "N meses").
 */
function formatMonths(months: number | null): string {
  if (months === null || months <= 0) return '—';
  const years = Math.floor(months / 12);
  const remainder = months - years * 12;
  if (years === 0) return `${remainder} ${remainder === 1 ? 'mes' : 'meses'}`;
  if (remainder === 0) return `${years} ${years === 1 ? 'año' : 'años'}`;
  return `${years}a ${remainder}m`;
}

/**
 * Card de salud financiera mobile (PHASE-22). Espejo de
 * `apps/web/components/dashboard/debt-health-card.tsx`.
 *
 * Muestra:
 * - Patrimonio neto (assets - liabilities) en grande, en danger si
 *   negativo.
 * - Subtotales Activos / Pasivos.
 * - Grid 2x3 de KPIs cuando hay deuda: DTI (con badge tonal), cuota
 *   mensual, APR ponderado, tiempo para saldar, intereses YTD,
 *   % en deuda.
 * - Empty state cuando `total_liabilities === 0`.
 */
export function DebtHealthCard() {
  const { data, isLoading, isError } = useDebtHealth();

  if (isLoading) {
    return (
      <View style={styles.card}>
        <Text style={styles.placeholder}>Cargando salud financiera…</Text>
      </View>
    );
  }

  if (isError || !data) {
    return (
      <View style={styles.card}>
        <Text style={styles.errorText}>
          Error cargando indicadores de deuda.
        </Text>
      </View>
    );
  }

  const totalLiabilitiesNum = Number(data.total_liabilities);
  const hasDebt = totalLiabilitiesNum > 0;
  const netWorthNum = Number(data.net_worth);
  const netWorthColor = netWorthNum < 0 ? colors.danger : colors.text;

  const dtiTone = dtiStatusColors(data.dti_status);
  const dtiPercent =
    data.dti_ratio !== null ? (data.dti_ratio * 100).toFixed(1) : null;
  const aprPercent =
    data.weighted_apr !== null ? (data.weighted_apr * 100).toFixed(2) : null;
  const debtToAssetsPercent =
    data.debt_to_assets_ratio !== null
      ? (data.debt_to_assets_ratio * 100).toFixed(1)
      : null;

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <View style={styles.iconBubble} accessibilityElementsHidden>
          <Text style={styles.iconBubbleText}>❤</Text>
        </View>
        <View style={{ flex: 1, minWidth: 0 }}>
          <Text style={styles.eyebrow}>Salud financiera</Text>
          <Text style={[styles.netWorth, { color: netWorthColor }]}>
            {formatAmount(data.net_worth, data.reference_currency)}
          </Text>
        </View>
      </View>

      <View style={styles.subtotalsRow}>
        <SubtotalRow
          label="Activos"
          value={formatAmount(data.total_assets, data.reference_currency)}
          color={colors.income}
        />
        <SubtotalRow
          label="Pasivos"
          value={`-${formatAmount(data.total_liabilities, data.reference_currency)}`}
          color={colors.danger}
        />
      </View>

      {hasDebt ? (
        <View style={styles.kpiGrid}>
          <Metric
            label="DTI"
            value={dtiPercent !== null ? `${dtiPercent}%` : '—'}
            badge={{ label: dtiTone.label, bg: dtiTone.bg, fg: dtiTone.fg }}
          />
          <Metric
            label="Cuota mensual"
            value={formatAmount(
              data.monthly_debt_payment,
              data.reference_currency,
            )}
          />
          <Metric
            label="APR medio"
            value={aprPercent !== null ? `${aprPercent}%` : '—'}
          />
          <Metric
            label="Tiempo para saldar"
            value={formatMonths(data.time_to_payoff_months)}
          />
          <Metric
            label="Intereses YTD"
            value={formatAmount(
              data.interest_paid_ytd,
              data.reference_currency,
            )}
            valueColor={colors.danger}
          />
          <Metric
            label="% en deuda"
            value={
              debtToAssetsPercent !== null ? `${debtToAssetsPercent}%` : '—'
            }
          />
        </View>
      ) : (
        <View style={styles.emptyBlock}>
          <Text style={styles.emptyText}>
            Sin deudas registradas. Cuando añadas una tarjeta, préstamo o
            hipoteca verás aquí ratios de salud financiera y proyección de
            pago.
          </Text>
        </View>
      )}
    </View>
  );
}

function SubtotalRow({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  return (
    <View style={styles.subtotal}>
      <Text style={styles.subtotalLabel}>{label}:</Text>
      <Text style={[styles.subtotalValue, { color }]}>{value}</Text>
    </View>
  );
}

interface MetricBadge {
  label: string;
  bg: string;
  fg: string;
}

function Metric({
  label,
  value,
  valueColor,
  badge,
}: {
  label: string;
  value: string;
  valueColor?: string;
  badge?: MetricBadge;
}) {
  return (
    <View style={styles.metric}>
      <Text style={styles.metricLabel}>{label}</Text>
      <View style={styles.metricValueRow}>
        <Text
          style={[styles.metricValue, { color: valueColor ?? colors.text }]}
          numberOfLines={1}
          adjustsFontSizeToFit
        >
          {value}
        </Text>
        {badge ? (
          <View style={[styles.metricBadge, { backgroundColor: badge.bg }]}>
            <Text style={[styles.metricBadgeText, { color: badge.fg }]}>
              {badge.label}
            </Text>
          </View>
        ) : null}
      </View>
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
  placeholder: {
    color: colors.textMuted,
    fontSize: fontSize.sm,
  },
  errorText: {
    color: colors.danger,
    fontSize: fontSize.sm,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  iconBubble: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconBubbleText: {
    fontSize: fontSize.md,
    color: colors.primary,
    lineHeight: fontSize.md + 4,
  },
  eyebrow: {
    fontSize: 11,
    fontWeight: fontWeight.semibold,
    color: colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  netWorth: {
    fontSize: fontSize.xl,
    fontWeight: fontWeight.bold,
    lineHeight: fontSize.xl + 4,
    marginTop: 2,
  },
  subtotalsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md,
  },
  subtotal: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: spacing.xs,
  },
  subtotalLabel: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    fontWeight: fontWeight.medium,
  },
  subtotalValue: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
  },
  kpiGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: spacing.md,
  },
  metric: {
    flexBasis: '48%',
    flexGrow: 1,
    gap: 2,
  },
  metricLabel: {
    fontSize: 11,
    fontWeight: fontWeight.medium,
    color: colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  metricValueRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    flexWrap: 'wrap',
  },
  metricValue: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    flexShrink: 1,
  },
  metricBadge: {
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: radius.sm,
  },
  metricBadgeText: {
    fontSize: 10,
    fontWeight: fontWeight.semibold,
    letterSpacing: 0.4,
  },
  emptyBlock: {
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: spacing.md,
  },
  emptyText: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    textAlign: 'center',
    lineHeight: 18,
  },
});
