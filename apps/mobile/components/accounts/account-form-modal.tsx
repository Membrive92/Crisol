import { useEffect, useState } from 'react';
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import type { Account, AccountType } from '@crisol/types';
import { ASSET_ACCOUNT_TYPES } from '@crisol/types';
import {
  DEFAULT_CATEGORY_COLOR,
  colors,
  fontSize,
  fontWeight,
  radius,
  spacing,
} from '@crisol/ui';

import { AccountAppearanceFields } from './account-appearance-fields';

export interface AccountFormValues {
  name: string;
  type: AccountType;
  currency: string;
  color: string;
  icon: string | null;
  /** Decimal serializado como string. Vacío equivale a "0". */
  opening_balance: string;
}

export interface AccountFormModalProps {
  visible: boolean;
  /** Si es null se interpreta como modo "crear", si no, modo "editar". */
  initial: Account | null;
  submitting?: boolean;
  /** Si se omite, el form muestra todos los campos. */
  variant?: 'full' | 'minimal';
  onSubmit: (data: AccountFormValues) => void;
  onCancel: () => void;
}

const TYPE_LABEL: Record<AccountType, string> = {
  bank: 'Banco',
  savings: 'Ahorro',
  brokerage: 'Bróker',
  crypto: 'Crypto',
  cash: 'Efectivo',
  // PHASE-20 — no se exponen en PHASE-19.1, los dejamos por exhaustividad.
  credit_card: 'Tarjeta',
  loan: 'Préstamo',
  mortgage: 'Hipoteca',
};

export const DEFAULT_ACCOUNT_FORM: AccountFormValues = {
  name: '',
  type: 'bank',
  currency: 'EUR',
  color: DEFAULT_CATEGORY_COLOR,
  icon: null,
  opening_balance: '',
};

function fromAccount(account: Account): AccountFormValues {
  return {
    name: account.name,
    type: account.type,
    currency: account.currency,
    color: account.color ?? DEFAULT_CATEGORY_COLOR,
    icon: account.icon,
    opening_balance:
      account.opening_balance && account.opening_balance !== '0.00'
        ? account.opening_balance
        : '',
  };
}

/**
 * Modal espejo de `CategoryFormModal` para crear/editar cuentas.
 * Se reutiliza desde la pantalla settings-style (modo `full`) y desde
 * el onboarding (modo `minimal` — sólo nombre + tipo + moneda).
 */
export function AccountFormModal({
  visible,
  initial,
  submitting,
  variant = 'full',
  onSubmit,
  onCancel,
}: AccountFormModalProps) {
  const [values, setValues] = useState<AccountFormValues>(DEFAULT_ACCOUNT_FORM);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!visible) return;
    setValues(initial ? fromAccount(initial) : DEFAULT_ACCOUNT_FORM);
    setError(null);
  }, [visible, initial]);

  function patch<K extends keyof AccountFormValues>(
    field: K,
    next: AccountFormValues[K],
  ) {
    setValues((prev) => ({ ...prev, [field]: next }));
  }

  function handleSubmit() {
    setError(null);
    const trimmedName = values.name.trim();
    if (!trimmedName) {
      setError('El nombre es obligatorio.');
      return;
    }
    const currency = values.currency.trim().toUpperCase();
    if (currency.length !== 3) {
      setError('Código ISO de 3 letras (ej: EUR).');
      return;
    }
    const opening = values.opening_balance.trim().replace(',', '.');
    if (opening && Number.isNaN(Number(opening))) {
      setError('Importe inicial inválido.');
      return;
    }
    onSubmit({
      ...values,
      name: trimmedName,
      currency,
      opening_balance: opening,
    });
  }

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent
      onRequestClose={onCancel}
    >
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <View style={styles.header}>
            <Text style={styles.title}>
              {initial ? 'Editar cuenta' : 'Nueva cuenta'}
            </Text>
            <Pressable onPress={onCancel} accessibilityRole="button">
              <Text style={styles.closeText}>✕</Text>
            </Pressable>
          </View>
          <ScrollView contentContainerStyle={styles.content}>
            <View>
              <Text style={styles.label}>Nombre</Text>
              <TextInput
                style={styles.input}
                value={values.name}
                onChangeText={(v) => patch('name', v)}
                maxLength={100}
                placeholder="Cuenta nómina, Ahorro Revolut, Caja…"
                placeholderTextColor={colors.textMuted}
              />
            </View>

            <View>
              <Text style={styles.label}>Tipo</Text>
              <View style={styles.typeGrid}>
                {ASSET_ACCOUNT_TYPES.map((opt) => {
                  const active = opt === values.type;
                  return (
                    <Pressable
                      key={opt}
                      onPress={() => patch('type', opt)}
                      style={[
                        styles.typeChip,
                        active && styles.typeChipActive,
                      ]}
                    >
                      <Text
                        style={[
                          styles.typeChipText,
                          active && styles.typeChipTextActive,
                        ]}
                      >
                        {TYPE_LABEL[opt]}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            </View>

            <View>
              <Text style={styles.label}>Moneda</Text>
              <TextInput
                style={[styles.input, styles.currencyInput]}
                value={values.currency}
                onChangeText={(v) => patch('currency', v.toUpperCase())}
                maxLength={3}
                autoCapitalize="characters"
                autoCorrect={false}
                placeholder="EUR"
                placeholderTextColor={colors.textMuted}
              />
            </View>

            {variant === 'full' ? (
              <>
                <View>
                  <Text style={styles.label}>Saldo inicial (opcional)</Text>
                  <TextInput
                    style={styles.input}
                    value={values.opening_balance}
                    onChangeText={(v) => patch('opening_balance', v)}
                    keyboardType="decimal-pad"
                    placeholder="0.00"
                    placeholderTextColor={colors.textMuted}
                  />
                </View>

                <AccountAppearanceFields
                  color={values.color}
                  icon={values.icon}
                  onColorChange={(hex) => patch('color', hex)}
                  onIconChange={(emoji) => patch('icon', emoji)}
                />
              </>
            ) : (
              <Text style={styles.helper}>
                Podrás añadir color, icono y saldo inicial más adelante desde
                Cuentas.
              </Text>
            )}

            {error ? <Text style={styles.error}>{error}</Text> : null}
          </ScrollView>
          <View style={styles.actions}>
            <Pressable onPress={onCancel} style={styles.actionGhost}>
              <Text style={styles.actionGhostText}>Cancelar</Text>
            </Pressable>
            <Pressable
              onPress={handleSubmit}
              disabled={submitting}
              style={[
                styles.actionPrimary,
                submitting && styles.actionPrimaryDisabled,
              ]}
            >
              <Text style={styles.actionPrimaryText}>
                {submitting ? 'Guardando…' : initial ? 'Guardar' : 'Crear'}
              </Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: colors.background,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    maxHeight: '92%',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  title: {
    fontSize: fontSize.lg,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  closeText: { fontSize: fontSize.lg, color: colors.textMuted },
  content: { padding: spacing.md, gap: spacing.md, paddingBottom: spacing.lg },
  label: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.medium,
    color: colors.text,
    marginBottom: spacing.xs,
  },
  input: {
    backgroundColor: colors.surface,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
    fontSize: fontSize.md,
    color: colors.text,
  },
  currencyInput: { maxWidth: 140, textTransform: 'uppercase' },
  typeGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
  },
  typeChip: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  typeChipActive: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primary,
  },
  typeChipText: {
    fontSize: fontSize.sm,
    color: colors.text,
    fontWeight: fontWeight.medium,
  },
  typeChipTextActive: {
    color: colors.primary,
    fontWeight: fontWeight.semibold,
  },
  helper: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    lineHeight: 18,
  },
  error: { color: colors.danger, fontSize: fontSize.sm },
  actions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: spacing.sm,
    padding: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  actionGhost: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
  },
  actionGhostText: { color: colors.textMuted, fontWeight: fontWeight.medium },
  actionPrimary: {
    backgroundColor: colors.primary,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.sm,
  },
  actionPrimaryDisabled: { opacity: 0.6 },
  actionPrimaryText: {
    color: colors.onPrimary,
    fontWeight: fontWeight.semibold,
  },
});
