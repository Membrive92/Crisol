import { useState } from 'react';
import { ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';

import { useCategories } from '@finanzas/services';
import type {
  Category,
  Transaction,
  TransactionCreateRequest,
  TransactionUpdateRequest,
} from '@finanzas/types';
import {
  colors,
  fontSize,
  fontWeight,
  fromDateInputValue,
  radius,
  spacing,
  toDateInputValue,
} from '@finanzas/ui';

interface TransactionFormValues {
  amount: string;
  currency: string;
  occurred_at: string;
  category_id: string;
  description: string;
}

export interface TransactionFormProps {
  initial?: Transaction;
  submitting?: boolean;
  submitLabel: string;
  onSubmit: (payload: TransactionCreateRequest | TransactionUpdateRequest) => void;
  onCancel?: () => void;
}

function buildInitialValues(initial?: Transaction): TransactionFormValues {
  return {
    amount: initial?.amount ?? '',
    currency: initial?.currency ?? 'EUR',
    occurred_at: toDateInputValue(initial?.occurred_at ?? new Date().toISOString()),
    category_id: initial?.category_id ?? '',
    description: initial?.description ?? '',
  };
}

export function TransactionForm({
  initial,
  submitting,
  submitLabel,
  onSubmit,
  onCancel,
}: TransactionFormProps) {
  const { data: categories } = useCategories();
  const [values, setValues] = useState<TransactionFormValues>(() => buildInitialValues(initial));
  const [error, setError] = useState<string | null>(null);

  function update<K extends keyof TransactionFormValues>(field: K, value: string) {
    setValues((prev) => ({ ...prev, [field]: value }));
  }

  function handleSubmit() {
    setError(null);
    const amount = values.amount.trim().replace(',', '.');
    if (!amount || Number.isNaN(Number(amount)) || Number(amount) <= 0) {
      setError('Importe debe ser un número positivo');
      return;
    }
    onSubmit({
      amount,
      currency: values.currency.trim().toUpperCase() || 'EUR',
      occurred_at: fromDateInputValue(values.occurred_at),
      category_id: values.category_id || null,
      description: values.description.trim() || null,
    });
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
    >
      <Text style={styles.label}>Importe</Text>
      <TextInput
        style={styles.input}
        value={values.amount}
        onChangeText={(v) => update('amount', v)}
        keyboardType="decimal-pad"
        placeholder="0.00"
        placeholderTextColor={colors.textSubtle}
      />

      <Text style={styles.label}>Moneda</Text>
      <TextInput
        style={styles.input}
        value={values.currency}
        onChangeText={(v) => update('currency', v)}
        maxLength={3}
        autoCapitalize="characters"
      />

      <Text style={styles.label}>Fecha (YYYY-MM-DD)</Text>
      <TextInput
        style={styles.input}
        value={values.occurred_at}
        onChangeText={(v) => update('occurred_at', v)}
        placeholder="2026-04-16"
        placeholderTextColor={colors.textSubtle}
      />

      <Text style={styles.label}>Categoría</Text>
      <View style={styles.categoryList}>
        <TouchableOpacity
          style={[styles.categoryChip, values.category_id === '' && styles.categoryChipActive]}
          onPress={() => update('category_id', '')}
        >
          <Text
            style={[
              styles.categoryChipText,
              values.category_id === '' && styles.categoryChipTextActive,
            ]}
          >
            Sin categoría
          </Text>
        </TouchableOpacity>
        {(categories ?? []).map((c: Category) => {
          const selected = values.category_id === c.id;
          return (
            <TouchableOpacity
              key={c.id}
              style={[styles.categoryChip, selected && styles.categoryChipActive]}
              onPress={() => update('category_id', c.id)}
            >
              <Text
                style={[styles.categoryChipText, selected && styles.categoryChipTextActive]}
              >
                {c.name}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>

      <Text style={styles.label}>Descripción</Text>
      <TextInput
        style={[styles.input, styles.textarea]}
        value={values.description}
        onChangeText={(v) => update('description', v)}
        multiline
        maxLength={500}
      />

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <TouchableOpacity
        style={[styles.submit, submitting && styles.submitDisabled]}
        onPress={handleSubmit}
        disabled={submitting}
      >
        <Text style={styles.submitText}>{submitting ? 'Guardando…' : submitLabel}</Text>
      </TouchableOpacity>
      {onCancel ? (
        <TouchableOpacity style={styles.cancel} onPress={onCancel}>
          <Text style={styles.cancelText}>Cancelar</Text>
        </TouchableOpacity>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.md },
  label: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.medium as '500',
    color: colors.text,
    marginBottom: spacing.xs,
    marginTop: spacing.sm,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    padding: spacing.sm,
    fontSize: fontSize.md,
    backgroundColor: colors.surface,
    color: colors.text,
  },
  textarea: { minHeight: 80, textAlignVertical: 'top' },
  categoryList: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs, marginBottom: spacing.sm },
  categoryChip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    backgroundColor: colors.surface,
  },
  categoryChipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  categoryChipText: { color: colors.text, fontSize: fontSize.sm },
  categoryChipTextActive: { color: colors.surface },
  error: { color: colors.danger, marginTop: spacing.sm, fontSize: fontSize.sm },
  submit: {
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    paddingVertical: spacing.sm,
    alignItems: 'center',
    marginTop: spacing.lg,
  },
  submitDisabled: { opacity: 0.6 },
  submitText: { color: colors.surface, fontSize: fontSize.md, fontWeight: fontWeight.semibold as '600' },
  cancel: {
    paddingVertical: spacing.sm,
    alignItems: 'center',
    marginTop: spacing.sm,
  },
  cancelText: { color: colors.textMuted, fontSize: fontSize.sm },
});
