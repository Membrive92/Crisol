import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { PieChart } from 'react-native-gifted-charts';

import type { CategoryBreakdownItem } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';
import { formatAmount } from '@crisol/ui';

export type DonutKindFilter = 'all' | 'income' | 'expense';

export interface CategoryDonutProps {
  data: CategoryBreakdownItem[] | undefined;
  currency: string;
  isLoading: boolean;
  kind: DonutKindFilter;
  onKindChange: (next: DonutKindFilter) => void;
  /** Cuántas categorías mostrar como slices independientes; el resto agrupa en "Otros". */
  topN?: number;
}

const PALETTE = [
  colors.primary,
  colors.warning,
  colors.success,
  colors.danger,
  colors.text,
  colors.borderStrong,
];

interface Slice {
  id: string;
  label: string;
  value: number;
  color: string;
  pct: number;
  isOther: boolean;
}

/**
 * Donut por categoría (PHASE-18.2 polish). Mejoras sobre la versión
 * pre-18.2:
 * - Top N + "Otros (k)" agrupado para evitar pies con 12 slices
 *   ilegibles.
 * - Leyenda lateral con amount + porcentaje por categoría (antes
 *   sólo nombre).
 * - Tap en una fila de la leyenda baja la opacidad del resto y
 *   resalta la elegida.
 * - Centro con Total en dos líneas (label + monto).
 */
export function CategoryDonut({
  data,
  currency,
  isLoading,
  kind,
  onKindChange,
  topN = 5,
}: CategoryDonutProps) {
  const [activeId, setActiveId] = useState<string | null>(null);

  const sorted = [...(data ?? [])].sort(
    (a, b) => Number(b.total) - Number(a.total),
  );
  const total = sorted.reduce((acc, x) => acc + Number(x.total), 0);
  const top = sorted.slice(0, topN);
  const rest = sorted.slice(topN);
  const restTotal = rest.reduce((acc, x) => acc + Number(x.total), 0);
  const empty = !isLoading && total === 0;

  const slices: Slice[] = [
    ...top.map((item, idx) => ({
      id: item.category_id ?? `_no_cat_${item.category_name}`,
      label: item.category_icon
        ? `${item.category_icon} ${item.category_name}`
        : item.category_name,
      value: Number(item.total),
      color:
        item.category_color ??
        PALETTE[idx % PALETTE.length] ??
        colors.primary,
      pct: total > 0 ? (Number(item.total) / total) * 100 : 0,
      isOther: false,
    })),
  ];
  if (rest.length > 0) {
    slices.push({
      id: '_other',
      label: `Otros (${rest.length})`,
      value: restTotal,
      color: colors.borderStrong,
      pct: total > 0 ? (restTotal / total) * 100 : 0,
      isOther: true,
    });
  }

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <Text style={styles.title}>Por categoría</Text>
        <View style={styles.toggle}>
          <ToggleButton active={kind === 'all'} onPress={() => onKindChange('all')}>
            Total
          </ToggleButton>
          <ToggleButton
            active={kind === 'expense'}
            onPress={() => onKindChange('expense')}
          >
            Gastos
          </ToggleButton>
          <ToggleButton
            active={kind === 'income'}
            onPress={() => onKindChange('income')}
          >
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
            data={slices.map((s) => ({
              value: s.value,
              color:
                activeId === null || activeId === s.id
                  ? s.color
                  : `${s.color}55`,
            }))}
            donut
            radius={70}
            innerRadius={45}
            innerCircleColor={colors.surface}
            centerLabelComponent={() => (
              <View style={styles.centerLabel}>
                <Text style={styles.centerLabelHint}>Total</Text>
                <Text style={styles.centerLabelText}>
                  {formatAmount(String(total.toFixed(2)), currency)}
                </Text>
              </View>
            )}
          />
          <View style={styles.legend}>
            {slices.map((s) => (
              <Pressable
                key={s.id}
                onPress={() =>
                  setActiveId((current) => (current === s.id ? null : s.id))
                }
                style={[
                  styles.legendRow,
                  activeId === s.id && styles.legendRowActive,
                ]}
              >
                <View style={[styles.legendDot, { backgroundColor: s.color }]} />
                <View style={{ flex: 1 }}>
                  <Text
                    numberOfLines={1}
                    style={[
                      styles.legendLabel,
                      s.isOther && { color: colors.textMuted },
                    ]}
                  >
                    {s.label}
                  </Text>
                  <Text style={styles.legendMeta}>
                    {formatAmount(String(s.value.toFixed(2)), currency)} ·{' '}
                    {s.pct.toFixed(0)}%
                  </Text>
                </View>
              </Pressable>
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
      <Text style={[styles.toggleText, active && styles.toggleTextActive]}>
        {children}
      </Text>
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
  centerLabelHint: { fontSize: 10, color: colors.textMuted, marginBottom: 2 },
  centerLabelText: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    color: colors.text,
    fontVariant: ['tabular-nums'] as const,
  },
  legend: { flex: 1, gap: 4 },
  legendRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 4,
    paddingHorizontal: 6,
    borderRadius: radius.sm,
  },
  legendRowActive: { backgroundColor: colors.surfaceMuted },
  legendDot: { width: 10, height: 10, borderRadius: 5 },
  legendLabel: {
    fontSize: fontSize.xs,
    color: colors.text,
    fontWeight: fontWeight.medium,
  },
  legendMeta: {
    fontSize: 10,
    color: colors.textMuted,
    fontVariant: ['tabular-nums'] as const,
    marginTop: 1,
  },
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
