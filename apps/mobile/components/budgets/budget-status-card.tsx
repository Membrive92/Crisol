import { StyleSheet, Text, View } from 'react-native';

import type { BudgetStatusItem, Category } from '@finanzas/types';
import { colors, fontSize, fontWeight, formatAmount, radius, spacing } from '@finanzas/ui';

export interface BudgetStatusCardProps {
  item: BudgetStatusItem;
  categories: Category[];
}

function paletteFor(status: BudgetStatusItem['status']): { accent: string } {
  switch (status) {
    case 'over':
      return { accent: colors.danger };
    case 'warning':
      return { accent: colors.warning };
    case 'ok':
    default:
      return { accent: colors.success };
  }
}

function findCategory(categories: Category[], id: string | null): Category | undefined {
  if (!id) return undefined;
  return categories.find((c) => c.id === id);
}

/**
 * Card mobile equivalente a la versión web — barra cap a 100%, badge
 * con `X% · status`, spent + remaining (en `Excedido` rojo si negativo).
 */
export function BudgetStatusCard({ item, categories }: BudgetStatusCardProps) {
  const { budget, spent_this_month, remaining, percent_used, status } = item;
  const palette = paletteFor(status);
  const category = findCategory(categories, budget.category_id);
  const label = category?.name ?? 'Global (todas las categorías)';
  const accent = category?.color ?? null;
  const emoji = category?.icon ?? null;
  const cappedPercent = Math.min(percent_used, 100);
  const isOver = Number(remaining) < 0;

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        {accent ? (
          <View style={[styles.swatch, { backgroundColor: accent }]}>
            {emoji ? <Text style={styles.swatchIcon}>{emoji}</Text> : null}
          </View>
        ) : null}
        <View style={{ flex: 1 }}>
          <Text style={styles.title} numberOfLines={1}>
            {label}
          </Text>
          <Text style={styles.subtitle}>
            Límite mensual {formatAmount(budget.amount, budget.currency)}
          </Text>
        </View>
        <View style={[styles.badge, { borderColor: palette.accent }]}>
          <Text style={[styles.badgeText, { color: palette.accent }]}>
            {percent_used.toFixed(0)}% · {status}
          </Text>
        </View>
      </View>

      <View style={styles.barTrack}>
        <View
          style={[
            styles.barFill,
            { width: `${cappedPercent}%`, backgroundColor: palette.accent },
          ]}
        />
      </View>

      <View style={styles.footer}>
        <Text style={styles.footerText}>
          Gastado{' '}
          <Text style={styles.footerStrong}>
            {formatAmount(spent_this_month, budget.currency)}
          </Text>
        </Text>
        <Text style={styles.footerText}>
          {isOver ? 'Excedido ' : 'Restante '}
          <Text
            style={[
              styles.footerStrong,
              isOver && { color: colors.danger },
            ]}
          >
            {formatAmount(
              isOver ? remaining.replace('-', '') : remaining,
              budget.currency,
            )}
          </Text>
        </Text>
      </View>

      {item.unconvertible_count > 0 ? (
        <Text style={styles.unconvertible}>
          ≈ {item.unconvertible_count}{' '}
          {item.unconvertible_count === 1 ? 'transacción' : 'transacciones'}{' '}
          sin tasa
        </Text>
      ) : null}
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
  },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  title: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  subtitle: { fontSize: fontSize.xs, color: colors.textMuted, marginTop: 2 },
  swatch: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  swatchIcon: { fontSize: fontSize.sm },
  badge: {
    borderWidth: 1,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: fontWeight.semibold,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  barTrack: {
    width: '100%',
    height: 8,
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.sm,
    overflow: 'hidden',
    marginBottom: spacing.sm,
  },
  barFill: { height: '100%' },
  footer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  footerText: { fontSize: fontSize.xs, color: colors.textMuted },
  footerStrong: { color: colors.text, fontWeight: fontWeight.semibold },
  unconvertible: {
    marginTop: spacing.xs,
    fontSize: fontSize.xs,
    color: colors.warning,
  },
});
