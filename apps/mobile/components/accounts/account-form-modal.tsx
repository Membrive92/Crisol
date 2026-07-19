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

import { useCategories } from '@crisol/services';
import type { Account, AccountType } from '@crisol/types';
import {
  AMORTIZABLE_ACCOUNT_TYPES,
  ASSET_ACCOUNT_TYPES,
  LIABILITY_ACCOUNT_TYPES,
} from '@crisol/types';
import {
  DEFAULT_CATEGORY_COLOR,
  colors,
  fontSize,
  fontWeight,
  radius,
  spacing,
} from '@crisol/ui';

import { AccountAppearanceFields } from './account-appearance-fields';
import { DateInput } from '../ui/date-input';

export interface AccountFormValues {
  name: string;
  type: AccountType;
  currency: string;
  color: string;
  icon: string | null;
  /** Decimal serializado como string. Vacío equivale a "0". */
  opening_balance: string;
  /**
   * TIN anual en porcentaje (UI), p.ej. "5.9" para 5.9%. Vacío = sin
   * valor. El caller transforma a decimal (`"0.0590"`) antes de enviar
   * al backend. PHASE-24.2: aplica a loan/mortgage/credit_card.
   */
  apr_percent: string;
  /** PHASE-24.2 — TAE anual (% UI). Informativa, no afecta cálculo. */
  tae_percent: string;
  /** Plazo total en meses como string. Vacío = sin valor. */
  term_months: string;
  /** Fecha de inicio del préstamo en `YYYY-MM-DD`. Vacío = sin valor. */
  start_date: string;
  /** PHASE-24.3 — Total contractualizado por el banco (€). */
  total_to_pay: string;
  /** PHASE-24.3 — Primer pago sólo de intereses (€). */
  interest_only_first_payment: string;
  /** PHASE-30.5 — Categoría de pagos vinculada (sólo liabilities).
   * Vacío = sin vincular. */
  category_id: string;
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
  credit_card: 'Tarjeta',
  loan: 'Préstamo',
  mortgage: 'Hipoteca',
};

const DEFAULT_ACCOUNT_FORM: AccountFormValues = {
  name: '',
  type: 'bank',
  currency: 'EUR',
  color: DEFAULT_CATEGORY_COLOR,
  icon: null,
  opening_balance: '',
  apr_percent: '',
  tae_percent: '',
  term_months: '',
  start_date: '',
  total_to_pay: '',
  interest_only_first_payment: '',
  category_id: '',
};

/**
 * Convierte un APR decimal serializado (ej. "0.035") al porcentaje que
 * se muestra en UI ("3.5"). Recorta ceros finales para que "0.04" →
 * "4". Devuelve cadena vacía si la entrada es null/no numérica.
 */
function aprDecimalToPercent(decimal: string | null): string {
  if (!decimal) return '';
  const numeric = Number(decimal);
  if (!Number.isFinite(numeric)) return '';
  return (numeric * 100).toString();
}

function isAmortizableType(type: AccountType): boolean {
  return AMORTIZABLE_ACCOUNT_TYPES.includes(type);
}

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
    apr_percent: aprDecimalToPercent(account.apr),
    tae_percent: aprDecimalToPercent(account.tae ?? null),
    term_months: account.term_months ? String(account.term_months) : '',
    start_date: account.start_date ?? '',
    total_to_pay: account.total_to_pay ?? '',
    interest_only_first_payment: account.interest_only_first_payment ?? '',
    category_id: account.category_id ?? '',
  };
}

/**
 * Modal espejo de `CategoryFormModal` para crear/editar cuentas
 * (PHASE-19.1, ampliado en PHASE-22 con campos de amortización).
 *
 * El picker de tipo separa "Activos" y "Pasivos / deuda" en dos chip
 * rows. Para `loan` y `mortgage` se muestran tres TextInput extra
 * (APR%, plazo en meses y fecha de inicio); al cambiar a otro tipo
 * esos campos se limpian para no enviar valores residuales.
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
  const categoriesQuery = useCategories();
  const debtCategories = (categoriesQuery.data ?? []).filter(
    (c) => c.role === 'DEBT_PAYMENT' || c.role === 'DEBT_INTEREST',
  );

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

  function handleTypeChange(nextType: AccountType) {
    const nextIsLiability = LIABILITY_ACCOUNT_TYPES.includes(nextType);
    // Al cambiar a un tipo no amortizable, limpiamos los campos
    // específicos para que el caller no envíe valores residuales.
    if (!isAmortizableType(nextType)) {
      setValues((prev) => ({
        ...prev,
        type: nextType,
        apr_percent: '',
        tae_percent: '',
        term_months: '',
        start_date: '',
        total_to_pay: '',
        interest_only_first_payment: '',
        // PHASE-30.5: category_id sólo aplica a liabilities. Al
        // cambiar a asset, limpiar para no enviar un vínculo inválido.
        category_id: nextIsLiability ? prev.category_id : '',
      }));
      return;
    }
    setValues((prev) => ({
      ...prev,
      type: nextType,
      category_id: nextIsLiability ? prev.category_id : '',
    }));
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
    if (isAmortizableType(values.type)) {
      const aprRaw = values.apr_percent.trim().replace(',', '.');
      if (aprRaw) {
        const apr = Number(aprRaw);
        if (!Number.isFinite(apr) || apr < 0) {
          setError('APR inválido (porcentaje, ej. 3.5).');
          return;
        }
      }
      const term = values.term_months.trim();
      if (term) {
        const months = Number(term);
        if (!Number.isInteger(months) || months <= 0) {
          setError('Plazo en meses debe ser un entero positivo.');
          return;
        }
      }
      const start = values.start_date.trim();
      if (start && !/^\d{4}-\d{2}-\d{2}$/.test(start)) {
        setError('Fecha en formato YYYY-MM-DD.');
        return;
      }
    }
    onSubmit({
      ...values,
      name: trimmedName,
      currency,
      opening_balance: opening,
    });
  }

  const isLiability = LIABILITY_ACCOUNT_TYPES.includes(values.type);
  const showAmortization = isAmortizableType(values.type);
  const balanceLabel = isLiability
    ? 'Capital (opcional)'
    : 'Saldo inicial (opcional)';

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
              <Text style={styles.subLabel}>Activos</Text>
              <View style={styles.typeGrid}>
                {ASSET_ACCOUNT_TYPES.map((opt) => {
                  const active = opt === values.type;
                  return (
                    <Pressable
                      key={opt}
                      onPress={() => handleTypeChange(opt)}
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
              <Text style={[styles.subLabel, styles.subLabelSpaced]}>
                Pasivos / deuda
              </Text>
              <View style={styles.typeGrid}>
                {LIABILITY_ACCOUNT_TYPES.map((opt) => {
                  const active = opt === values.type;
                  return (
                    <Pressable
                      key={opt}
                      onPress={() => handleTypeChange(opt)}
                      style={[
                        styles.typeChip,
                        styles.typeChipLiability,
                        active && styles.typeChipLiabilityActive,
                      ]}
                    >
                      <Text
                        style={[
                          styles.typeChipText,
                          active && styles.typeChipLiabilityTextActive,
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
                  <Text style={styles.label}>{balanceLabel}</Text>
                  <TextInput
                    style={[
                      styles.input,
                      isLiability && { color: colors.danger },
                    ]}
                    value={values.opening_balance}
                    onChangeText={(v) => patch('opening_balance', v)}
                    keyboardType="decimal-pad"
                    placeholder="0.00"
                    placeholderTextColor={colors.textMuted}
                  />
                </View>

                {isLiability ? (
                  <View>
                    <Text style={styles.label}>
                      Categoría de pagos vinculada (opcional)
                    </Text>
                    {debtCategories.length === 0 ? (
                      <Text style={styles.helper}>
                        Aún no tienes categorías marcadas como deuda.
                        Crea una en Ajustes › Categorías y marca el tipo
                        "Pago de deuda" o "Intereses de deuda" para que
                        aparezca aquí.
                      </Text>
                    ) : (
                      <>
                        <View style={styles.categoryChipRow}>
                          <Pressable
                            onPress={() => patch('category_id', '')}
                            style={[
                              styles.categoryChip,
                              !values.category_id && styles.categoryChipActive,
                            ]}
                          >
                            <Text
                              style={[
                                styles.categoryChipText,
                                !values.category_id && styles.categoryChipTextActive,
                              ]}
                            >
                              Sin vincular
                            </Text>
                          </Pressable>
                          {debtCategories.map((c) => {
                            const active = values.category_id === c.id;
                            return (
                              <Pressable
                                key={c.id}
                                onPress={() => patch('category_id', c.id)}
                                style={[
                                  styles.categoryChip,
                                  active && styles.categoryChipActive,
                                ]}
                              >
                                <Text
                                  style={[
                                    styles.categoryChipText,
                                    active && styles.categoryChipTextActive,
                                  ]}
                                  numberOfLines={1}
                                >
                                  {c.icon ? `${c.icon} ` : ''}
                                  {c.name}
                                </Text>
                              </Pressable>
                            );
                          })}
                        </View>
                        <Text style={styles.helper}>
                          Si las cuotas de este contrato aparecen como una
                          categoría en tus transacciones, vincúlala para
                          cruzar Capa 1 (flujo) con Capa 2 (saldo).
                        </Text>
                      </>
                    )}
                  </View>
                ) : null}

                {showAmortization ? (
                  <View style={styles.amortBox}>
                    <Text style={styles.amortLegend}>
                      Cuadro de amortización (francés)
                    </Text>
                    <Text style={styles.amortHelp}>
                      Rellena TIN, plazo y fecha de inicio para calcular
                      cuota e intereses. TAE es informativa.
                    </Text>
                    <View>
                      <Text style={styles.label}>TIN anual (%)</Text>
                      <TextInput
                        style={styles.input}
                        value={values.apr_percent}
                        onChangeText={(v) => patch('apr_percent', v)}
                        keyboardType="decimal-pad"
                        placeholder="5,90"
                        placeholderTextColor={colors.textMuted}
                      />
                    </View>
                    <View>
                      <Text style={styles.label}>TAE anual (%) opc.</Text>
                      <TextInput
                        style={styles.input}
                        value={values.tae_percent}
                        onChangeText={(v) => patch('tae_percent', v)}
                        keyboardType="decimal-pad"
                        placeholder="6,12"
                        placeholderTextColor={colors.textMuted}
                      />
                    </View>
                    <View>
                      <Text style={styles.label}>Plazo (meses)</Text>
                      <TextInput
                        style={styles.input}
                        value={values.term_months}
                        onChangeText={(v) => patch('term_months', v)}
                        keyboardType="number-pad"
                        placeholder="12"
                        placeholderTextColor={colors.textMuted}
                      />
                    </View>
                    <DateInput
                      label="Fecha de inicio"
                      value={values.start_date}
                      onChange={(v) => patch('start_date', v)}
                    />
                    <View>
                      <Text style={styles.label}>Total a pagar (€) opc.</Text>
                      <TextInput
                        style={styles.input}
                        value={values.total_to_pay}
                        onChangeText={(v) => patch('total_to_pay', v)}
                        keyboardType="decimal-pad"
                        placeholder="913,86"
                        placeholderTextColor={colors.textMuted}
                      />
                    </View>
                    <View>
                      <Text style={styles.label}>
                        1er pago sólo intereses (€) opc.
                      </Text>
                      <TextInput
                        style={styles.input}
                        value={values.interest_only_first_payment}
                        onChangeText={(v) =>
                          patch('interest_only_first_payment', v)
                        }
                        keyboardType="decimal-pad"
                        placeholder="0,00"
                        placeholderTextColor={colors.textMuted}
                      />
                    </View>
                  </View>
                ) : null}

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
  subLabel: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.semibold,
    color: colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginBottom: spacing.xs,
  },
  subLabelSpaced: { marginTop: spacing.sm },
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
  typeChipLiability: {
    backgroundColor: colors.surface,
  },
  typeChipLiabilityActive: {
    backgroundColor: colors.dangerSoft,
    borderColor: colors.danger,
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
  typeChipLiabilityTextActive: {
    color: colors.danger,
    fontWeight: fontWeight.semibold,
  },
  categoryChipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
    marginTop: spacing.xs,
    marginBottom: spacing.xs,
  },
  categoryChip: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    maxWidth: 200,
  },
  categoryChipActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primarySoft,
  },
  categoryChipText: {
    fontSize: 12,
    fontWeight: fontWeight.semibold,
    color: colors.textMuted,
  },
  categoryChipTextActive: {
    color: colors.primary,
  },
  amortBox: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surfaceMuted,
    padding: spacing.md,
    gap: spacing.sm,
  },
  amortLegend: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.semibold,
    color: colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  amortHelp: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    lineHeight: 16,
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
