import { StyleSheet, Text, View } from 'react-native';

import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
} from '@crisol/ui';

export interface PaymentsSummaryCardProps {
  /** Título con el período, p. ej. "Pagos a deuda — Abril 2025". */
  title: string;
  totalPayments: string;
  interestsAndFees: string;
  capitalAmortized: string;
  currency: string;
  isLoading: boolean;
}

/**
 * PHASE-30.5 — Mobile parity de `payments-summary-card.tsx` (web).
 * KPI grande, barra apilada y desglose Capital vs Intereses. El selector
 * de período vive fuera (PHASE-30.8, `PeriodNavigator`); la card recibe
 * el período ya resuelto como `title`.
 */
export function PaymentsSummaryCard({
  title,
  totalPayments,
  interestsAndFees,
  capitalAmortized,
  currency,
  isLoading,
}: PaymentsSummaryCardProps) {
  const total = Number(totalPayments);
  const interests = Number(interestsAndFees);
  const interestPct = total > 0 ? Math.round((interests / total) * 100) : 0;
  const capitalPct = total > 0 ? 100 - interestPct : 0;
  const empty = !isLoading && total === 0;

  return (
    <View style={styles.card}>
      <View style={styles.headerRow}>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>{title}</Text>
          <Text style={styles.subtitle}>
            Todo lo destinado a categorías marcadas como deuda en este periodo.
          </Text>
        </View>
      </View>

      {empty ? (
        <Text style={styles.emptyBox}>
          Sin pagos a deuda registrados en este periodo. Categoriza una
          transacción como deuda para ver el desglose.
        </Text>
      ) : (
        <>
          <Text style={styles.bigValue}>
            {isLoading ? '—' : formatAmount(totalPayments, currency)}
          </Text>

          <View style={styles.barTrack}>
            <View
              style={{
                width: `${capitalPct}%`,
                backgroundColor: colors.primary,
              }}
            />
            <View
              style={{
                width: `${interestPct}%`,
                backgroundColor: colors.danger,
              }}
            />
          </View>

          <View style={styles.breakdownRow}>
            <Breakdown
              swatch={colors.primary}
              title="Capital amortizado"
              amount={formatAmount(capitalAmortized, currency)}
              pct={capitalPct}
            />
            <Breakdown
              swatch={colors.danger}
              title="Intereses y comisiones"
              amount={formatAmount(interestsAndFees, currency)}
              pct={interestPct}
            />
          </View>
        </>
      )}
    </View>
  );
}

function Breakdown({
  swatch,
  title,
  amount,
  pct,
}: {
  swatch: string;
  title: string;
  amount: string;
  pct: number;
}) {
  return (
    <View style={styles.breakdownItem}>
      <View style={styles.breakdownTitle}>
        <View style={[styles.dot, { backgroundColor: swatch }]} />
        <Text style={styles.breakdownTitleText}>{title}</Text>
      </View>
      <Text style={styles.breakdownAmount}>
        {amount} <Text style={styles.breakdownPct}>· {pct}%</Text>
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
    gap: spacing.md,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    flexWrap: 'wrap',
  },
  title: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  subtitle: {
    marginTop: spacing.xs,
    fontSize: fontSize.xs,
    color: colors.textMuted,
    lineHeight: 18,
  },
  emptyBox: {
    backgroundColor: colors.surfaceMuted,
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: colors.border,
    borderRadius: radius.sm,
    padding: spacing.md,
    fontSize: fontSize.sm,
    color: colors.textMuted,
    lineHeight: 20,
  },
  bigValue: {
    fontSize: fontSize.xxl,
    fontWeight: fontWeight.bold,
    color: colors.text,
    letterSpacing: -0.5,
  },
  barTrack: {
    flexDirection: 'row',
    height: 14,
    width: '100%',
    borderRadius: 999,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceMuted,
  },
  breakdownRow: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  breakdownItem: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    padding: spacing.sm,
    gap: 2,
  },
  breakdownTitle: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 999,
  },
  breakdownTitleText: {
    fontSize: 11,
    color: colors.textMuted,
    fontWeight: fontWeight.medium,
  },
  breakdownAmount: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  breakdownPct: {
    fontWeight: fontWeight.regular,
    color: colors.textMuted,
    fontSize: 11,
  },
});
