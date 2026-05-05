import { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import type { Budget, Category } from '@finanzas/types';
import { colors, fontSize, fontWeight, formatAmount, radius, spacing } from '@finanzas/ui';

export interface BudgetActiveRowProps {
  budget: Budget;
  categories: Category[];
  onSave: (id: string, amount: string) => Promise<void> | void;
  onDelete: (id: string, label: string) => void;
  busy?: boolean;
}

/**
 * Row de presupuesto activo con modo lectura/edición. Mismo
 * contrato que `BudgetRow` web — el caller pasa onSave / onDelete y
 * el row gestiona su propio modo y validación local.
 */
export function BudgetActiveRow({
  budget: b,
  categories,
  onSave,
  onDelete,
  busy = false,
}: BudgetActiveRowProps) {
  const cat = categories.find((c) => c.id === b.category_id);
  const label = cat?.name ?? 'Global';
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<string>(b.amount);
  const [error, setError] = useState<string | null>(null);

  function handleStart() {
    setDraft(b.amount);
    setError(null);
    setEditing(true);
  }

  function handleCancel() {
    setEditing(false);
    setError(null);
  }

  async function handleSave() {
    const trimmed = draft.trim().replace(',', '.');
    if (!trimmed || Number.isNaN(Number(trimmed)) || Number(trimmed) <= 0) {
      setError('El importe debe ser un número positivo.');
      return;
    }
    setError(null);
    await onSave(b.id, trimmed);
    setEditing(false);
  }

  return (
    <View style={styles.row}>
      <View style={{ flex: 1 }}>
        <Text style={styles.title}>{label}</Text>
        {editing ? (
          <View style={styles.editRow}>
            <TextInput
              autoFocus
              value={draft}
              onChangeText={setDraft}
              keyboardType="decimal-pad"
              style={styles.input}
              placeholder="0.00"
            />
            <Text style={styles.editSuffix}>{b.currency} / mes</Text>
            {error ? <Text style={styles.error}>{error}</Text> : null}
          </View>
        ) : (
          <Text style={styles.meta}>
            {formatAmount(b.amount, b.currency)} / mes · desde {b.effective_from}
          </Text>
        )}
      </View>
      <View style={styles.actions}>
        {editing ? (
          <>
            <Pressable
              onPress={handleSave}
              disabled={busy}
              style={({ pressed }) => [
                styles.primaryButton,
                pressed && styles.pressed,
                busy && styles.disabled,
              ]}
            >
              <Text style={styles.primaryButtonText}>
                {busy ? 'Guardando…' : 'Guardar'}
              </Text>
            </Pressable>
            <Pressable
              onPress={handleCancel}
              disabled={busy}
              style={({ pressed }) => [
                styles.secondaryButton,
                pressed && styles.pressed,
              ]}
            >
              <Text style={styles.secondaryButtonText}>Cancelar</Text>
            </Pressable>
          </>
        ) : (
          <>
            <Pressable
              onPress={handleStart}
              disabled={busy}
              style={({ pressed }) => [
                styles.secondaryButton,
                pressed && styles.pressed,
                busy && styles.disabled,
              ]}
            >
              <Text style={styles.secondaryButtonText}>Editar</Text>
            </Pressable>
            <Pressable
              onPress={() => onDelete(b.id, label)}
              disabled={busy}
              style={({ pressed }) => [
                styles.secondaryButton,
                pressed && styles.pressed,
                busy && styles.disabled,
              ]}
            >
              <Text style={[styles.secondaryButtonText, { color: colors.danger }]}>
                {busy ? 'Cerrando…' : 'Cerrar'}
              </Text>
            </Pressable>
          </>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    gap: spacing.sm,
  },
  title: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  meta: { fontSize: fontSize.xs, color: colors.textMuted, marginTop: 2 },
  editRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: spacing.xs,
    marginTop: spacing.xs,
  },
  input: {
    width: 100,
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    fontSize: fontSize.sm,
    color: colors.text,
    backgroundColor: colors.background,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.sm,
  },
  editSuffix: { fontSize: fontSize.xs, color: colors.textMuted },
  error: { fontSize: fontSize.xs, color: colors.danger, width: '100%' },
  actions: { flexDirection: 'column', gap: spacing.xs },
  primaryButton: {
    paddingVertical: 6,
    paddingHorizontal: spacing.sm + 2,
    borderRadius: radius.sm,
    backgroundColor: colors.primary,
  },
  primaryButtonText: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.semibold,
    color: colors.onPrimary,
  },
  secondaryButton: {
    paddingVertical: 6,
    paddingHorizontal: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
  },
  secondaryButtonText: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  pressed: { opacity: 0.7 },
  disabled: { opacity: 0.5 },
});
