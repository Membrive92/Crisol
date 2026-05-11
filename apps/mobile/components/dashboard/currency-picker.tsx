import { useState } from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

export interface CurrencyPickerProps {
  value: string;
  onChange: (next: string) => void;
  /** Lista de monedas con datos del usuario. Vacía → cae a `FALLBACK_CURRENCIES`. */
  currencies?: string[] | undefined;
}

const FALLBACK_CURRENCIES = ['EUR', 'USD'] as const;

/**
 * Chip + sheet de monedas — versión slim de `DashboardFilters` sin el
 * picker de año (Análisis usa `PeriodToggle` para la ventana temporal).
 */
export function CurrencyPicker({ value, onChange, currencies }: CurrencyPickerProps) {
  const [open, setOpen] = useState(false);
  const base =
    currencies && currencies.length > 0 ? currencies : (FALLBACK_CURRENCIES as readonly string[]);
  const options = base.includes(value) ? base : [...base, value];

  return (
    <View style={styles.row}>
      <Pressable onPress={() => setOpen(true)} style={styles.chip}>
        <Text style={styles.chipText}>Moneda: {value}</Text>
      </Pressable>

      <Modal
        transparent
        visible={open}
        animationType="fade"
        onRequestClose={() => setOpen(false)}
      >
        <Pressable style={styles.backdrop} onPress={() => setOpen(false)}>
          <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
            <Text style={styles.sheetTitle}>Selecciona moneda</Text>
            {options.map((c) => (
              <Pressable
                key={c}
                onPress={() => {
                  onChange(c);
                  setOpen(false);
                }}
                style={[styles.option, c === value && styles.optionSelected]}
              >
                <Text style={[styles.optionText, c === value && styles.optionTextSelected]}>
                  {c}
                </Text>
              </Pressable>
            ))}
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', marginBottom: spacing.md },
  chip: {
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md,
    borderRadius: radius.lg,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipText: { fontSize: fontSize.sm, color: colors.text, fontWeight: fontWeight.medium },
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.4)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.lg,
  },
  sheet: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.md,
    width: '100%',
    maxWidth: 320,
  },
  sheetTitle: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
    marginBottom: spacing.sm,
  },
  option: { paddingVertical: spacing.sm, paddingHorizontal: spacing.md, borderRadius: radius.md },
  optionSelected: { backgroundColor: colors.primary },
  optionText: { fontSize: fontSize.md, color: colors.text },
  optionTextSelected: { color: colors.onPrimary, fontWeight: fontWeight.semibold },
});
