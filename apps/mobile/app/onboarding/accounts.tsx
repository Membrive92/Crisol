import { useEffect, useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useRouter } from 'expo-router';

import {
  formatApiError,
  useAccounts,
  useCreateAccount,
} from '@crisol/services';
import { toast } from '@crisol/store';
import type { AccountCreateRequest, AccountType } from '@crisol/types';
import { ASSET_ACCOUNT_TYPES } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  radius,
  spacing,
} from '@crisol/ui';

const REDIRECT_TARGET = '/(modules)/personal-finance/(tabs)/analysis';

const TYPE_LABEL: Record<AccountType, string> = {
  bank: 'Banco',
  savings: 'Ahorro',
  brokerage: 'Bróker',
  crypto: 'Crypto',
  cash: 'Efectivo',
  credit_card: 'Tarjeta',
  loan: 'Préstamo',
  mortgage: 'Hipoteca',
};

interface FormState {
  name: string;
  type: AccountType;
  currency: string;
}

const DEFAULT_FORM: FormState = {
  name: '',
  type: 'bank',
  currency: 'EUR',
};

/**
 * Pantalla bloqueante de "primera cuenta" (PHASE-19.1).
 * Form mínimo: nombre + tipo + moneda. Tras crear la cuenta, el guard
 * del root layout deja de redirigir aquí y el resto de pantallas
 * funcionan normalmente.
 */
export default function OnboardingAccountsScreen() {
  const router = useRouter();
  const accountsQuery = useAccounts();
  const create = useCreateAccount();
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [error, setError] = useState<string | null>(null);

  // Si ya tiene cuentas (refresh tras crear, navegación manual…), salir.
  useEffect(() => {
    if (accountsQuery.data && accountsQuery.data.length > 0) {
      router.replace(REDIRECT_TARGET);
    }
  }, [accountsQuery.data, router]);

  function patch<K extends keyof FormState>(field: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function handleSubmit() {
    setError(null);
    const trimmedName = form.name.trim();
    if (!trimmedName) {
      setError('El nombre es obligatorio.');
      return;
    }
    const currency = form.currency.trim().toUpperCase();
    if (currency.length !== 3) {
      setError('Código ISO de 3 letras (ej: EUR).');
      return;
    }
    const payload: AccountCreateRequest = {
      name: trimmedName,
      type: form.type,
      currency,
    };
    create.mutate(payload, {
      onSuccess: () => {
        toast.success('Cuenta creada. ¡A registrar!');
        router.replace(REDIRECT_TARGET);
      },
      onError: (err) => setError(formatApiError(err, 'No se pudo crear.')),
    });
  }

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      style={styles.container}
    >
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>Bienvenido</Text>
        <Text style={styles.subtitle}>
          Antes de empezar, declara tu primera cuenta — necesitarás imputar
          cada transacción a una cuenta para que los KPIs sean correctos.
        </Text>

        <View style={styles.card}>
          <Text style={styles.label}>Nombre</Text>
          <TextInput
            style={styles.input}
            value={form.name}
            onChangeText={(v) => patch('name', v)}
            maxLength={100}
            placeholder="Cuenta nómina, Ahorro Revolut, Caja…"
            placeholderTextColor={colors.textMuted}
            autoFocus
          />

          <Text style={styles.label}>Tipo</Text>
          <View style={styles.typeGrid}>
            {ASSET_ACCOUNT_TYPES.map((opt) => {
              const active = opt === form.type;
              return (
                <Pressable
                  key={opt}
                  onPress={() => patch('type', opt)}
                  style={[styles.typeChip, active && styles.typeChipActive]}
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

          <Text style={styles.label}>Moneda</Text>
          <TextInput
            style={[styles.input, styles.currencyInput]}
            value={form.currency}
            onChangeText={(v) => patch('currency', v.toUpperCase())}
            maxLength={3}
            autoCapitalize="characters"
            autoCorrect={false}
          />

          <Text style={styles.helper}>
            Podrás añadir color, icono y saldo inicial más adelante desde
            Cuentas.
          </Text>

          {error ? <Text style={styles.error}>{error}</Text> : null}

          <Pressable
            onPress={handleSubmit}
            disabled={create.isPending}
            style={({ pressed }) => [
              styles.submit,
              (pressed || create.isPending) && { opacity: 0.7 },
            ]}
          >
            <Text style={styles.submitText}>
              {create.isPending ? 'Creando…' : 'Crear cuenta'}
            </Text>
          </Pressable>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: spacing.lg,
  },
  title: {
    fontSize: fontSize.xxl,
    fontWeight: fontWeight.bold,
    color: colors.text,
    textAlign: 'center',
    marginBottom: spacing.sm,
  },
  subtitle: {
    fontSize: fontSize.md,
    color: colors.textMuted,
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: spacing.lg,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
    gap: spacing.sm,
  },
  label: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.medium,
    color: colors.text,
    marginTop: spacing.sm,
  },
  input: {
    backgroundColor: colors.background,
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
    backgroundColor: colors.background,
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
    marginTop: spacing.xs,
  },
  error: { color: colors.danger, fontSize: fontSize.sm, marginTop: spacing.xs },
  submit: {
    marginTop: spacing.md,
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    paddingVertical: spacing.sm,
    alignItems: 'center',
  },
  submitText: {
    color: colors.onPrimary,
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
  },
});
