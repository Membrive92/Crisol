import { useState } from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

export interface DashboardFiltersValue {
  currency: string;
  year: number;
}

export interface DashboardFiltersProps {
  value: DashboardFiltersValue;
  onChange: (next: DashboardFiltersValue) => void;
}

const CURRENCIES = ['USD', 'EUR'] as const;

function buildYearOptions(): number[] {
  const current = new Date().getFullYear();
  return Array.from({ length: 5 }, (_, i) => current - i);
}

type Picker = 'currency' | 'year' | null;

export function DashboardFilters({ value, onChange }: DashboardFiltersProps) {
  const [picker, setPicker] = useState<Picker>(null);
  const yearOptions = buildYearOptions();

  return (
    <View style={styles.row}>
      <Chip label={`Moneda: ${value.currency}`} onPress={() => setPicker('currency')} />
      <Chip label={`Año: ${value.year}`} onPress={() => setPicker('year')} />

      <Modal
        transparent
        visible={picker !== null}
        animationType="fade"
        onRequestClose={() => setPicker(null)}
      >
        <Pressable style={styles.backdrop} onPress={() => setPicker(null)}>
          <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
            <Text style={styles.sheetTitle}>
              {picker === 'currency' ? 'Selecciona moneda' : 'Selecciona año'}
            </Text>
            {picker === 'currency' &&
              CURRENCIES.map((c) => (
                <SheetOption
                  key={c}
                  label={c}
                  selected={c === value.currency}
                  onPress={() => {
                    onChange({ ...value, currency: c });
                    setPicker(null);
                  }}
                />
              ))}
            {picker === 'year' &&
              yearOptions.map((y) => (
                <SheetOption
                  key={y}
                  label={String(y)}
                  selected={y === value.year}
                  onPress={() => {
                    onChange({ ...value, year: y });
                    setPicker(null);
                  }}
                />
              ))}
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

function Chip({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={styles.chip}>
      <Text style={styles.chipText}>{label}</Text>
    </Pressable>
  );
}

function SheetOption({
  label,
  selected,
  onPress,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable onPress={onPress} style={[styles.option, selected && styles.optionSelected]}>
      <Text style={[styles.optionText, selected && styles.optionTextSelected]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.md, flexWrap: 'wrap' },
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
  optionTextSelected: { color: colors.surface, fontWeight: fontWeight.semibold },
});
