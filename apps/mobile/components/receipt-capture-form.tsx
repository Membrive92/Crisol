import { useEffect, useState } from 'react';
import { StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';

import { pickPreferredAccountId, useAccounts, useCategories } from '@crisol/services';
import type { Account, ReceiptConfirmRequest, ReceiptExtraction } from '@crisol/types';
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

export interface ReceiptCaptureFormProps {
  extraction: ReceiptExtraction | Record<string, unknown>;
  submitting?: boolean;
  errorMessage?: string | null;
  onSubmit: (payload: ReceiptConfirmRequest) => void;
  onReject?: () => void;
}

interface FormValues {
  account_id: string;
  amount: string;
  currency: string;
  occurred_at: string; // YYYY-MM-DD
  description: string;
  category_id: string;
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function buildInitialValues(
  extraction: ReceiptExtraction | Record<string, unknown>,
  defaultAccountId: string,
): FormValues {
  const ext = extraction as Record<string, unknown>;
  const occurred = asString(ext['occurred_at']);
  return {
    account_id: defaultAccountId,
    amount: asString(ext['total']),
    currency: asString(ext['currency']) || 'EUR',
    occurred_at: occurred ? toDateInputValue(occurred) : toDateInputValue(new Date().toISOString()),
    description: asString(ext['merchant']),
    category_id: '',
  };
}

export function ReceiptCaptureForm({
  extraction,
  submitting,
  errorMessage,
  onSubmit,
  onReject,
}: ReceiptCaptureFormProps) {
  const { data: categories } = useCategories();
  // PHASE-19.1: el confirm de un ticket exige `account_id`. Pre-selecciona
  // la primera activa; si el usuario no tiene ninguna mostramos warning
  // y desactivamos el submit (el guard de onboarding debería haber evitado
  // llegar aquí, pero defensivo).
  const { data: accounts } = useAccounts();
  // AUDIT-2026-07 (LOW): PHASE-35 — las compras a plazos hijas
  // (`parent_account_id`) no son destino de un ticket; se ocultan como en web.
  const activeAccounts: Account[] = (accounts ?? []).filter(
    (a) => !a.is_archived && !a.parent_account_id,
  );
  // PHASE-32: pre-selecciona la cuenta principal; fallback al primer activo.
  const defaultAccountId = pickPreferredAccountId(activeAccounts);

  const [values, setValues] = useState<FormValues>(() =>
    buildInitialValues(extraction, defaultAccountId),
  );
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    if (!values.account_id && defaultAccountId) {
      setValues((prev) => ({ ...prev, account_id: defaultAccountId }));
    }
  }, [defaultAccountId, values.account_id]);

  function handleChange<K extends keyof FormValues>(field: K, value: string) {
    setValues((prev) => ({ ...prev, [field]: value }));
  }

  function handleSubmit() {
    setValidationError(null);

    if (!values.account_id) {
      setValidationError('Selecciona una cuenta.');
      return;
    }
    const amount = values.amount.trim().replace(',', '.');
    if (!amount || Number.isNaN(Number(amount)) || Number(amount) <= 0) {
      setValidationError('Importe debe ser un número positivo');
      return;
    }
    const currency = values.currency.trim().toUpperCase();
    if (currency.length !== 3) {
      setValidationError('Moneda en formato ISO de 3 letras');
      return;
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(values.occurred_at)) {
      setValidationError('Fecha en formato YYYY-MM-DD');
      return;
    }

    const payload: ReceiptConfirmRequest = {
      account_id: values.account_id,
      amount,
      currency,
      occurred_at: fromDateInputValue(values.occurred_at),
      description: values.description.trim() || null,
      category_id: values.category_id || null,
    };
    onSubmit(payload);
  }

  const noAccounts = activeAccounts.length === 0;

  return (
    <View>
      <Text style={styles.helper}>
        Edita los datos extraídos antes de confirmar — la transacción se crea con los valores
        definitivos.
      </Text>

      <Text style={styles.label}>Cuenta</Text>
      {noAccounts ? (
        <Text style={styles.warning}>
          No tienes cuentas activas. Crea una desde Análisis → Cuentas para poder confirmar el
          ticket.
        </Text>
      ) : (
        <View style={styles.categoryRow}>
          {activeAccounts.map((a) => {
            const active = values.account_id === a.id;
            return (
              <TouchableOpacity
                key={a.id}
                style={[styles.categoryChip, active && styles.categoryChipActive]}
                onPress={() => handleChange('account_id', a.id)}
              >
                <Text style={[styles.categoryChipText, active && styles.categoryChipTextActive]}>
                  {a.icon ? `${a.icon} ` : ''}
                  {a.name} ({a.currency})
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
      )}

      <Text style={styles.label}>Importe</Text>
      <TextInput
        style={styles.input}
        value={values.amount}
        onChangeText={(v) => handleChange('amount', v)}
        keyboardType="decimal-pad"
        placeholder="0.00"
      />

      <Text style={styles.label}>Moneda (ISO)</Text>
      <TextInput
        style={styles.input}
        value={values.currency}
        onChangeText={(v) => handleChange('currency', v.toUpperCase())}
        autoCapitalize="characters"
        maxLength={3}
      />

      <View style={{ marginBottom: spacing.md }}>
        <DateInput
          label="Fecha"
          value={values.occurred_at}
          onChange={(v) => handleChange('occurred_at', v)}
        />
      </View>

      <Text style={styles.label}>Descripción</Text>
      <TextInput
        style={styles.input}
        value={values.description}
        onChangeText={(v) => handleChange('description', v)}
        placeholder="Comercio o detalle"
      />

      <Text style={styles.label}>Categoría (opcional)</Text>
      <View style={styles.categoryRow}>
        <TouchableOpacity
          style={[styles.categoryChip, !values.category_id && styles.categoryChipActive]}
          onPress={() => handleChange('category_id', '')}
        >
          <Text
            style={[styles.categoryChipText, !values.category_id && styles.categoryChipTextActive]}
          >
            Sin categoría
          </Text>
        </TouchableOpacity>
        {(categories ?? []).map((c) => {
          const active = values.category_id === c.id;
          return (
            <TouchableOpacity
              key={c.id}
              style={[styles.categoryChip, active && styles.categoryChipActive]}
              onPress={() => handleChange('category_id', c.id)}
            >
              <Text style={[styles.categoryChipText, active && styles.categoryChipTextActive]}>
                {c.name}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {validationError ? <Text style={styles.error}>{validationError}</Text> : null}
      {errorMessage ? <Text style={styles.error}>{errorMessage}</Text> : null}

      <View style={styles.buttonRow}>
        <TouchableOpacity
          style={[styles.primaryButton, (submitting || noAccounts) && styles.disabled]}
          onPress={handleSubmit}
          disabled={submitting || noAccounts}
        >
          <Text style={styles.primaryButtonText}>{submitting ? 'Guardando…' : 'Confirmar'}</Text>
        </TouchableOpacity>
        {onReject ? (
          <TouchableOpacity
            style={[styles.dangerButton, submitting && styles.disabled]}
            onPress={onReject}
            disabled={submitting}
          >
            <Text style={styles.dangerButtonText}>Rechazar</Text>
          </TouchableOpacity>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  helper: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    marginBottom: spacing.md,
  },
  label: {
    fontSize: fontSize.sm,
    color: colors.text,
    fontWeight: fontWeight.medium as '500',
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
    backgroundColor: colors.surface,
    marginBottom: spacing.md,
  },
  categoryRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
    marginBottom: spacing.md,
  },
  categoryChip: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  categoryChipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  categoryChipText: {
    fontSize: fontSize.xs,
    color: colors.text,
  },
  categoryChipTextActive: {
    color: colors.surface,
    fontWeight: fontWeight.semibold as '600',
  },
  warning: {
    color: colors.warning,
    fontSize: fontSize.sm,
    marginBottom: spacing.sm,
    lineHeight: 18,
  },
  error: {
    color: colors.danger,
    fontSize: fontSize.sm,
    marginBottom: spacing.sm,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  primaryButton: {
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    flex: 1,
    alignItems: 'center',
  },
  primaryButtonText: {
    color: colors.surface,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold as '600',
  },
  dangerButton: {
    backgroundColor: colors.danger,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    alignItems: 'center',
  },
  dangerButtonText: {
    color: colors.surface,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold as '600',
  },
  disabled: { opacity: 0.5 },
});
