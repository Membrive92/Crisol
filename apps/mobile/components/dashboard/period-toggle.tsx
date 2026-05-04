import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

export type PeriodKey = 'month' | 'quarter' | 'year';

export interface PeriodToggleProps {
  value: PeriodKey;
  onChange: (next: PeriodKey) => void;
}

const LABELS: Record<PeriodKey, string> = {
  month: 'Mes',
  quarter: 'Trimestre',
  year: 'Año',
};

const OPTIONS: PeriodKey[] = ['month', 'quarter', 'year'];

/**
 * Segmented Mes/Trimestre/Año equivalente a `StitchPeriodToggle` en
 * web pero con `Pressable` nativo. Los rangos los calcula
 * `rangeForPeriod` aquí mismo — duplicado consciente respecto a la
 * versión web (15 líneas). Si crece, mover a `packages/ui`.
 */
export function PeriodToggle({ value, onChange }: PeriodToggleProps) {
  return (
    <View style={styles.row}>
      {OPTIONS.map((opt) => {
        const active = opt === value;
        return (
          <Pressable
            key={opt}
            onPress={() => onChange(opt)}
            style={[styles.option, active && styles.optionActive]}
          >
            <Text style={[styles.optionText, active && styles.optionTextActive]}>
              {LABELS[opt]}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function rangeForPeriod(period: PeriodKey): { dateFrom: string; dateTo: string } {
  const now = new Date();
  if (period === 'month') {
    const start = new Date(now.getFullYear(), now.getMonth(), 1);
    const end = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59);
    return { dateFrom: start.toISOString(), dateTo: end.toISOString() };
  }
  if (period === 'quarter') {
    const q = Math.floor(now.getMonth() / 3);
    const start = new Date(now.getFullYear(), q * 3, 1);
    const end = new Date(now.getFullYear(), q * 3 + 3, 0, 23, 59, 59);
    return { dateFrom: start.toISOString(), dateTo: end.toISOString() };
  }
  const start = new Date(now.getFullYear(), 0, 1);
  const end = new Date(now.getFullYear(), 11, 31, 23, 59, 59);
  return { dateFrom: start.toISOString(), dateTo: end.toISOString() };
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 2,
    alignSelf: 'flex-start',
    marginBottom: spacing.md,
  },
  option: {
    paddingVertical: 6,
    paddingHorizontal: spacing.md,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  optionActive: {
    backgroundColor: colors.surface,
    borderColor: colors.borderStrong,
  },
  optionText: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    color: colors.textMuted,
  },
  optionTextActive: {
    color: colors.text,
  },
});
