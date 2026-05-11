import { useState } from 'react';
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import type { BudgetCreateRequest, Category } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

import { DateInput } from '../ui/date-input';

export interface BudgetFormModalProps {
  visible: boolean;
  categories: Category[];
  currencies?: string[];
  submitting?: boolean;
  onSubmit: (data: BudgetCreateRequest) => void;
  onCancel: () => void;
}

const DEFAULT_CURRENCY = 'EUR';

function todayISO(): string {
  const today = new Date();
  return [
    today.getFullYear(),
    String(today.getMonth() + 1).padStart(2, '0'),
    String(today.getDate()).padStart(2, '0'),
  ].join('-');
}

/**
 * Modal mobile para crear un presupuesto. Sólo categorías
 * `kind='expense'` aparecen — los budgets miden gasto. La currency
 * se hidrata de `useUserCurrencies` (cae a EUR si la lista está vacía).
 *
 * Validación local: amount > 0, fecha YYYY-MM-DD. El 409 del backend
 * lo gestiona el caller con un toast.
 */
export function BudgetFormModal({
  visible,
  categories,
  currencies,
  submitting,
  onSubmit,
  onCancel,
}: BudgetFormModalProps) {
  const [categoryId, setCategoryId] = useState<string>('');
  const [amount, setAmount] = useState<string>('');
  const [currency, setCurrency] = useState<string>(currencies?.[0] ?? DEFAULT_CURRENCY);
  const [effectiveFrom, setEffectiveFrom] = useState<string>(todayISO());
  const [convertOther, setConvertOther] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const expenseCategories = categories.filter((c) => c.kind === 'expense');
  const currencyOptions =
    currencies && currencies.length > 0 ? currencies : [DEFAULT_CURRENCY];

  function handleSubmit() {
    setError(null);
    const trimmed = amount.trim().replace(',', '.');
    if (!trimmed || Number.isNaN(Number(trimmed)) || Number(trimmed) <= 0) {
      setError('El importe debe ser un número positivo.');
      return;
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(effectiveFrom)) {
      setError('La fecha debe estar en formato YYYY-MM-DD.');
      return;
    }
    onSubmit({
      ...(categoryId ? { category_id: categoryId } : { category_id: null }),
      amount: trimmed,
      currency: currency.toUpperCase(),
      effective_from: effectiveFrom,
      convert_other_currencies: convertOther,
    });
  }

  return (
    <Modal
      transparent
      visible={visible}
      animationType="slide"
      onRequestClose={onCancel}
    >
      <Pressable style={styles.backdrop} onPress={onCancel}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <Text style={styles.heading}>Nuevo presupuesto</Text>
          <ScrollView contentContainerStyle={{ gap: spacing.md }}>
            <View>
              <Text style={styles.label}>Categoría</Text>
              <View style={styles.chipRow}>
                <Chip
                  label="Global"
                  active={categoryId === ''}
                  onPress={() => setCategoryId('')}
                />
                {expenseCategories.map((c) => (
                  <Chip
                    key={c.id}
                    label={c.name}
                    active={categoryId === c.id}
                    onPress={() => setCategoryId(c.id)}
                  />
                ))}
              </View>
            </View>

            <View style={{ flexDirection: 'row', gap: spacing.sm }}>
              <View style={{ flex: 1 }}>
                <Text style={styles.label}>Importe mensual</Text>
                <TextInput
                  style={styles.input}
                  value={amount}
                  onChangeText={setAmount}
                  keyboardType="decimal-pad"
                  placeholder="300.00"
                />
              </View>
              <View style={{ width: 110 }}>
                <Text style={styles.label}>Moneda</Text>
                <View style={styles.chipRowVertical}>
                  {currencyOptions.map((c) => (
                    <Chip
                      key={c}
                      label={c}
                      active={currency === c}
                      onPress={() => setCurrency(c)}
                    />
                  ))}
                </View>
              </View>
            </View>

            <DateInput
              label="Vigente desde"
              value={effectiveFrom}
              onChange={setEffectiveFrom}
            />

            <Pressable
              onPress={() => setConvertOther((v) => !v)}
              style={({ pressed }) => [
                styles.toggleRow,
                pressed && { opacity: 0.7 },
              ]}
              accessibilityRole="switch"
              accessibilityState={{ checked: convertOther }}
            >
              <View
                style={[
                  styles.checkbox,
                  convertOther && styles.checkboxActive,
                ]}
              >
                {convertOther ? <Text style={styles.checkmark}>✓</Text> : null}
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.toggleLabel}>
                  Sumar transacciones en otras monedas
                </Text>
                <Text style={styles.toggleHint}>
                  Convierte cada gasto a {currency.toUpperCase()} con la
                  tasa del día.
                </Text>
              </View>
            </Pressable>

            {error ? <Text style={styles.error}>{error}</Text> : null}
          </ScrollView>

          <View style={styles.actions}>
            <Pressable
              onPress={onCancel}
              style={({ pressed }) => [
                styles.secondaryButton,
                pressed && styles.pressed,
              ]}
            >
              <Text style={styles.secondaryButtonText}>Cancelar</Text>
            </Pressable>
            <Pressable
              onPress={handleSubmit}
              disabled={submitting}
              style={({ pressed }) => [
                styles.primaryButton,
                pressed && styles.pressed,
                submitting && { opacity: 0.5 },
              ]}
            >
              <Text style={styles.primaryButtonText}>
                {submitting ? 'Creando…' : 'Crear'}
              </Text>
            </Pressable>
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

function Chip({
  label,
  active,
  onPress,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.chip,
        active && styles.chipActive,
        pressed && styles.pressed,
      ]}
    >
      <Text style={[styles.chipText, active && styles.chipTextActive]}>
        {label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.4)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    padding: spacing.lg,
    maxHeight: '85%',
  },
  heading: {
    fontSize: fontSize.lg,
    fontWeight: fontWeight.semibold,
    color: colors.text,
    marginBottom: spacing.md,
  },
  label: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.medium,
    color: colors.text,
    marginBottom: spacing.xs,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
    fontSize: fontSize.md,
    color: colors.text,
    backgroundColor: colors.background,
  },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs },
  chipRowVertical: { flexDirection: 'column', gap: spacing.xs },
  chip: {
    paddingHorizontal: spacing.sm + 2,
    paddingVertical: 6,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { fontSize: fontSize.xs, color: colors.text },
  chipTextActive: { color: colors.onPrimary, fontWeight: fontWeight.semibold },
  toggleRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    paddingVertical: spacing.xs,
  },
  checkbox: {
    width: 20,
    height: 20,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 2,
  },
  checkboxActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  checkmark: {
    color: colors.onPrimary,
    fontSize: 14,
    lineHeight: 14,
    fontWeight: fontWeight.bold,
  },
  toggleLabel: {
    fontSize: fontSize.sm,
    color: colors.text,
    fontWeight: fontWeight.medium,
  },
  toggleHint: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    marginTop: 2,
  },
  error: { color: colors.danger, fontSize: fontSize.sm },
  actions: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  primaryButton: {
    flex: 1,
    backgroundColor: colors.primary,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    alignItems: 'center',
  },
  primaryButtonText: {
    color: colors.onPrimary,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
  },
  secondaryButton: {
    flex: 1,
    backgroundColor: 'transparent',
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  secondaryButtonText: {
    color: colors.text,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.medium,
  },
  pressed: { opacity: 0.7 },
});
