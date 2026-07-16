import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

// PHASE-41 — se eliminó `quarter` (sin sentido para un particular). `custom`
// es el rango libre `from/to` que define el usuario.
export type PeriodKey = 'month' | 'year' | 'custom';

export interface PeriodToggleProps {
  value: PeriodKey;
  onChange: (next: PeriodKey) => void;
  /** Opciones a mostrar; por defecto sin `custom` (opt-in del consumidor). */
  options?: readonly PeriodKey[];
}

const LABELS: Record<PeriodKey, string> = {
  month: 'Mes',
  year: 'Año',
  custom: 'Rango',
};

const DEFAULT_OPTIONS: readonly PeriodKey[] = ['month', 'year'];

/**
 * Segmented Mes/Año/Rango equivalente a `StitchPeriodToggle` en
 * web pero con `Pressable` nativo. Los rangos month/year los calcula
 * `rangeForPeriod` aquí mismo; el rango libre `custom` usa
 * `boundsForCustomRange` (compartido en `@crisol/services`).
 */
export function PeriodToggle({
  value,
  onChange,
  options = DEFAULT_OPTIONS,
}: PeriodToggleProps) {
  return (
    <View style={styles.row}>
      {options.map((opt) => {
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

export function rangeForPeriod(
  period: Exclude<PeriodKey, 'custom'>,
): { dateFrom: string; dateTo: string } {
  const now = new Date();
  if (period === 'month') {
    const start = new Date(now.getFullYear(), now.getMonth(), 1);
    const end = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59);
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
