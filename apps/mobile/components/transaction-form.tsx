import { useEffect, useState } from 'react';
import { ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';

import { pickPreferredAccountId, useAccounts, useCategories } from '@crisol/services';
import type {
  Account,
  Category,
  Transaction,
  TransactionCreateRequest,
  TransactionFlow,
  TransactionUpdateRequest,
} from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  fromDateInputValue,
  radius,
  spacing,
  toDateInputValue,
} from '@crisol/ui';

import { DateInput } from './ui/date-input';

// PHASE-34 (paridad con web) — dirección que el usuario declara con el
// segmento [Gasto]/[Ingreso]. Es la fuente de verdad del signo del saldo
// (ADR-0004); NO se deriva de la categoría.
type Direction = 'OUT' | 'IN';

function directionFromFlow(flow: TransactionFlow | null | undefined): Direction {
  return flow === 'IN' || flow === 'TRANSFER_IN' ? 'IN' : 'OUT';
}

interface TransactionFormValues {
  account_id: string;
  amount: string;
  currency: string;
  occurred_at: string;
  category_id: string;
  description: string;
  direction: Direction;
}

export interface TransactionFormProps {
  initial?: Transaction;
  submitting?: boolean;
  submitLabel: string;
  onSubmit: (payload: TransactionCreateRequest | TransactionUpdateRequest) => void;
  onCancel?: () => void;
}

function buildInitialValues(
  initial: Transaction | undefined,
  defaultAccountId: string,
): TransactionFormValues {
  return {
    account_id: initial?.account_id ?? defaultAccountId,
    amount: initial?.amount ?? '',
    currency: initial?.currency ?? 'EUR',
    occurred_at: toDateInputValue(initial?.occurred_at ?? new Date().toISOString()),
    category_id: initial?.category_id ?? '',
    description: initial?.description ?? '',
    // PHASE-34: por defecto Gasto; en edición se toma del flow existente.
    direction: directionFromFlow(initial?.flow),
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
  // PHASE-19.1: cuentas son obligatorias. Filtramos archivadas para
  // crear/editar — si la cuenta original de un edit está archivada se
  // mantiene en values.account_id (la mostramos sólo si coincide para
  // no perder el binding), pero el usuario no puede pasarse a otra
  // archivada desde el form.
  const { data: accounts } = useAccounts();
  // AUDIT-2026-07 (LOW): PHASE-35 — las compras a plazos hijas
  // (`parent_account_id`) no son destino de transacciones manuales; se ocultan
  // del selector como en web. Se conserva la cuenta ya asignada al editar para
  // no perder el binding.
  const activeAccounts: Account[] = (accounts ?? []).filter(
    (a) =>
      !a.is_archived && (!a.parent_account_id || a.id === initial?.account_id),
  );
  // PHASE-32: pre-selecciona la cuenta principal; fallback al primer activo.
  const defaultAccountId = pickPreferredAccountId(activeAccounts);

  const [values, setValues] = useState<TransactionFormValues>(() =>
    buildInitialValues(initial, defaultAccountId),
  );
  const [error, setError] = useState<string | null>(null);

  // PHASE-34 (paridad con web): una transferencia emparejada no usa el
  // segmento Gasto/Ingreso — su dirección la fija el par y el backend la
  // protege (409). El segmento sólo aplica a movimientos normales y altas.
  const isTransfer =
    initial != null &&
    (initial.transfer_pair_id != null ||
      initial.flow === 'TRANSFER_IN' ||
      initial.flow === 'TRANSFER_OUT');

  // Sincroniza account_id si las cuentas cargan después del montaje del
  // form (p.ej. crear desde un FAB sin pre-fetch). Sólo aplica si el
  // valor sigue vacío — no pisamos una elección manual del usuario.
  useEffect(() => {
    if (!values.account_id && defaultAccountId) {
      setValues((prev) => ({ ...prev, account_id: defaultAccountId }));
    }
  }, [defaultAccountId, values.account_id]);

  function update<K extends keyof TransactionFormValues>(field: K, value: string) {
    setValues((prev) => ({ ...prev, [field]: value }));
  }

  function handleSubmit() {
    setError(null);
    if (!values.account_id) {
      setError('Selecciona una cuenta.');
      return;
    }
    const amount = values.amount.trim().replace(',', '.');
    if (!amount || Number.isNaN(Number(amount)) || Number(amount) <= 0) {
      setError('Importe debe ser un número positivo');
      return;
    }
    const payload: TransactionCreateRequest = {
      account_id: values.account_id,
      amount,
      currency: values.currency.trim().toUpperCase() || 'EUR',
      occurred_at: fromDateInputValue(values.occurred_at),
      category_id: values.category_id || null,
      description: values.description.trim() || null,
    };
    // PHASE-34 (H-06): enviamos `flow` explícito desde el segmento. En una
    // transferencia emparejada NO lo tocamos (lo fija el par; el backend
    // rechaza romperlo). Antes el móvil nunca mandaba flow, así que toda
    // edición re-derivaba el flow desde la categoría en el backend y podía
    // invertir el signo del saldo en silencio (y una tx sin categoría
    // quedaba con flow=null, invisible para el saldo).
    if (!isTransfer) {
      payload.flow = values.direction;
    }
    onSubmit(payload);
  }

  const noAccounts = activeAccounts.length === 0;

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
    >
      <Text style={styles.label}>Cuenta</Text>
      {noAccounts ? (
        <Text style={styles.warning}>
          No tienes cuentas activas. Crea una desde Análisis → Cuentas para poder registrar
          transacciones.
        </Text>
      ) : (
        <View style={styles.categoryList}>
          {activeAccounts.map((a) => {
            const selected = values.account_id === a.id;
            return (
              <TouchableOpacity
                key={a.id}
                style={[styles.categoryChip, selected && styles.categoryChipActive]}
                onPress={() => update('account_id', a.id)}
              >
                <Text style={[styles.categoryChipText, selected && styles.categoryChipTextActive]}>
                  {a.icon ? `${a.icon} ` : ''}
                  {a.name} ({a.currency})
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
      )}

      {!isTransfer ? (
        <>
          <Text style={styles.label}>Tipo</Text>
          <View style={styles.segment}>
            {(['OUT', 'IN'] as Direction[]).map((d) => {
              const selected = values.direction === d;
              return (
                <TouchableOpacity
                  key={d}
                  style={[styles.segmentBtn, selected && styles.segmentBtnActive]}
                  onPress={() => setValues((prev) => ({ ...prev, direction: d }))}
                >
                  <Text
                    style={[styles.segmentText, selected && styles.segmentTextActive]}
                  >
                    {d === 'OUT' ? 'Gasto' : 'Ingreso'}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </>
      ) : null}

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

      <View style={{ marginBottom: spacing.md }}>
        <DateInput
          label="Fecha"
          value={values.occurred_at}
          onChange={(v) => update('occurred_at', v)}
        />
      </View>

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
              <Text style={[styles.categoryChipText, selected && styles.categoryChipTextActive]}>
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
        style={[styles.submit, (submitting || noAccounts) && styles.submitDisabled]}
        onPress={handleSubmit}
        disabled={submitting || noAccounts}
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
  categoryList: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
    marginBottom: spacing.sm,
  },
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
  segment: {
    flexDirection: 'row',
    gap: spacing.xs,
    marginBottom: spacing.sm,
  },
  segmentBtn: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    paddingVertical: spacing.sm,
    alignItems: 'center',
    backgroundColor: colors.surface,
  },
  segmentBtnActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  segmentText: { color: colors.text, fontSize: fontSize.sm, fontWeight: fontWeight.medium as '500' },
  segmentTextActive: { color: colors.surface, fontWeight: fontWeight.semibold as '600' },
  warning: {
    color: colors.warning,
    fontSize: fontSize.sm,
    marginBottom: spacing.sm,
    lineHeight: 18,
  },
  error: { color: colors.danger, marginTop: spacing.sm, fontSize: fontSize.sm },
  submit: {
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    paddingVertical: spacing.sm,
    alignItems: 'center',
    marginTop: spacing.lg,
  },
  submitDisabled: { opacity: 0.6 },
  submitText: {
    color: colors.surface,
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold as '600',
  },
  cancel: {
    paddingVertical: spacing.sm,
    alignItems: 'center',
    marginTop: spacing.sm,
  },
  cancelText: { color: colors.textMuted, fontSize: fontSize.sm },
});
