import { useState } from 'react';
import { Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import DateTimePicker, {
  type DateTimePickerEvent,
} from '@react-native-community/datetimepicker';

import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

export interface DateInputProps {
  /** Valor en formato `YYYY-MM-DD`. Vacío = hoy. */
  value: string;
  /** Recibe el nuevo valor en `YYYY-MM-DD`. */
  onChange: (value: string) => void;
  /** Etiqueta opcional encima del control. */
  label?: string;
  /** Placeholder cuando no hay valor (rara vez visible). */
  placeholder?: string;
  /** Mínima fecha seleccionable. */
  minimumDate?: Date;
  /** Máxima fecha seleccionable. */
  maximumDate?: Date;
}

function todayISO(): string {
  const d = new Date();
  return [
    d.getFullYear(),
    String(d.getMonth() + 1).padStart(2, '0'),
    String(d.getDate()).padStart(2, '0'),
  ].join('-');
}

function parseISO(value: string): Date {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return new Date();
  const [y, m, d] = value.split('-').map(Number) as [number, number, number];
  return new Date(y, m - 1, d);
}

function formatDateForDisplay(value: string): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  const [y, m, d] = value.split('-');
  return `${d}/${m}/${y}`;
}

/**
 * Date picker mobile cross-platform (PHASE-14.3). Reemplaza los
 * `<TextInput>` con formato `YYYY-MM-DD` tipeado a mano que se
 * usaban en transaction-form, budget-form-modal y
 * receipt-capture-form.
 *
 * Comportamiento por plataforma:
 * - iOS: el picker se muestra inline (`spinner`/`compact` según
 *   versión iOS). Tap fuera no aplica — usamos un toggle Pressable
 *   que muestra/oculta el picker.
 * - Android: el picker se invoca como modal nativo (`mode="default"`).
 *   El usuario selecciona y se cierra solo.
 *
 * El componente normaliza ambos comportamientos vía el state
 * `pickerOpen`. Siempre emite el valor en ISO `YYYY-MM-DD`.
 */
export function DateInput({
  value,
  onChange,
  label,
  placeholder = 'Selecciona fecha',
  minimumDate,
  maximumDate,
}: DateInputProps) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const dateValue = value ? parseISO(value) : new Date();

  function handleChange(event: DateTimePickerEvent, selected?: Date) {
    // Android emite event.type 'set' o 'dismissed'. iOS sólo 'set'
    // (el componente sigue visible hasta que el usuario lo cierra
    // con el toggle). En ambos casos, si hay `selected` emitimos.
    if (Platform.OS === 'android') {
      setPickerOpen(false);
      if (event.type === 'dismissed') return;
    }
    if (selected) {
      const iso = [
        selected.getFullYear(),
        String(selected.getMonth() + 1).padStart(2, '0'),
        String(selected.getDate()).padStart(2, '0'),
      ].join('-');
      onChange(iso);
    }
  }

  return (
    <View>
      {label ? <Text style={styles.label}>{label}</Text> : null}
      <Pressable
        onPress={() => setPickerOpen((open) => !open)}
        style={({ pressed }) => [styles.field, pressed && { opacity: 0.85 }]}
      >
        <Text style={[styles.fieldText, !value && styles.fieldPlaceholder]}>
          {value ? formatDateForDisplay(value) : placeholder}
        </Text>
      </Pressable>
      {pickerOpen ? (
        <DateTimePicker
          value={dateValue}
          mode="date"
          display={Platform.OS === 'ios' ? 'inline' : 'default'}
          onChange={handleChange}
          {...(minimumDate ? { minimumDate } : {})}
          {...(maximumDate ? { maximumDate } : {})}
        />
      ) : null}
    </View>
  );
}

DateInput.todayISO = todayISO;

const styles = StyleSheet.create({
  label: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.medium,
    color: colors.text,
    marginBottom: spacing.xs,
  },
  field: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
    backgroundColor: colors.surface,
  },
  fieldText: { fontSize: fontSize.md, color: colors.text },
  fieldPlaceholder: { color: colors.textSubtle },
});
