import { Pressable, StyleSheet, Text, View } from 'react-native';
import { PieChart } from 'react-native-gifted-charts';

import type { CategoryBreakdownItem } from '@finanzas/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';
import { formatAmount } from '@finanzas/ui';

export type DonutKindFilter = 'all' | 'income' | 'expense';

export interface CategoryDonutProps {
  data: CategoryBreakdownItem[] | undefined;
  currency: string;
  isLoading: boolean;
  kind: DonutKindFilter;
  onKindChange: (next: DonutKindFilter) => void;
}

const PALETTE = [
  '#1976d2',
  '#d32f2f',
  '#2e7d32',
  '#ed6c02',
  '#7b1fa2',
  '#0288d1',
  '#c2185b',
  '#5d4037',
  '#455a64',
  '#558b2f',
];

export function CategoryDonut({
  data,
  currency,
  isLoading,
  kind,
  onKindChange,
}: CategoryDonutProps) {
  const items = (data ?? []).map((item, idx) => ({
    name: item.category_name,
    value: Number(item.total),
    color: PALETTE[idx % PALETTE.length] ?? colors.primary,
  }));
  const total = items.reduce((acc, x) => acc + x.value, 0);
  const empty = !isLoading && items.length === 0;

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <Text style={styles.title}>Por categoría</Text>
        <View style={styles.toggle}>
          <ToggleButton active={kind === 'all'} onPress={() => onKindChange('all')}>
            Total
          </ToggleButton>
          <ToggleButton active={kind === 'expense'} onPress={() => onKindChange('expense')}>
            Gastos
          </ToggleButton>
          <ToggleButton active={kind === 'income'} onPress={() => onKindChange('income')}>
            Ingresos
          </ToggleButton>
        </View>
      </View>

      {isLoading && !data ? (
        <Text style={styles.placeholder}>Cargando…</Text>
      ) : empty ? (
        <Text style={styles.placeholder}>Sin datos en el periodo.</Text>
      ) : (
        <View style={styles.body}>
          <PieChart
            data={items.map((i) => ({ value: i.value, color: i.color }))}
            donut
            radius={70}
            innerRadius={45}
            innerCircleColor={colors.surface}
            centerLabelComponent={() => (
              <View style={styles.centerLabel}>
                <Text style={styles.centerLabelText}>{formatAmount(String(total), currency)}</Text>
              </View>
            )}
          />
          <View style={styles.legend}>
            {items.map((item) => (
              <View key={item.name} style={styles.legendItem}>
                <View style={[styles.legendDot, { backgroundColor: item.color }]} />
                <Text style={styles.legendText} numberOfLines={1}>
                  {item.name}
                </Text>
              </View>
            ))}
          </View>
        </View>
      )}
    </View>
  );
}

function ToggleButton({
  active,
  onPress,
  children,
}: {
  active: boolean;
  onPress: () => void;
  children: React.ReactNode;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={[styles.toggleButton, active && styles.toggleButtonActive]}
    >
      <Text style={[styles.toggleText, active && styles.toggleTextActive]}>{children}</Text>
    </Pressable>
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
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
  },
  title: { fontSize: fontSize.md, fontWeight: fontWeight.semibold, color: colors.text },
  placeholder: { color: colors.textMuted, fontSize: fontSize.sm },
  body: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  centerLabel: { alignItems: 'center', justifyContent: 'center' },
  centerLabelText: { fontSize: fontSize.sm, fontWeight: fontWeight.semibold, color: colors.text },
  legend: { flex: 1, gap: 4 },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  legendDot: { width: 10, height: 10, borderRadius: 5 },
  legendText: { fontSize: fontSize.xs, color: colors.textMuted, flexShrink: 1 },
  toggle: {
    flexDirection: 'row',
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    overflow: 'hidden',
  },
  toggleButton: { paddingVertical: 4, paddingHorizontal: 10, backgroundColor: colors.surface },
  toggleButtonActive: { backgroundColor: colors.primary },
  toggleText: { fontSize: fontSize.xs, color: colors.text, fontWeight: fontWeight.medium },
  toggleTextActive: { color: colors.onPrimary },
});
