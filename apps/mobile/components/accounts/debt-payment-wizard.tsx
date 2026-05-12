import { useEffect, useMemo, useState } from 'react';
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import {
  formatApiError,
  useAccounts,
  useAmortizationSchedule,
  useCategories,
  useCreateTransaction,
  useLinkTransfer,
} from '@crisol/services';
import { toast } from '@crisol/store';
import type { Account, AccountType, AmortizationRow } from '@crisol/types';
import { ASSET_ACCOUNT_TYPES } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  fromDateInputValue,
  radius,
  spacing,
  toDateInputValue,
} from '@crisol/ui';

import { DateInput } from '../ui/date-input';

export interface DebtPaymentWizardProps {
  liabilityAccount: Account;
  visible: boolean;
  onClose: () => void;
}

const INTEREST_CATEGORY_BY_TYPE: Partial<Record<AccountType, string>> = {
  mortgage: 'Intereses hipoteca',
  loan: 'Intereses préstamo',
  credit_card: 'Intereses tarjeta',
};

/**
 * Devuelve la fila del cuadro francés cuya fecha corresponde al mes
 * actual (o `undefined` si no aplica). Sirve para precargar el split
 * principal/intereses con los valores teóricos del préstamo.
 */
function findCurrentMonthRow(rows: AmortizationRow[]): AmortizationRow | undefined {
  const now = new Date();
  const target = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  return rows.find((row) => row.due_date.startsWith(target));
}

function parseAmount(value: string): number {
  const trimmed = value.trim().replace(',', '.');
  if (!trimmed) return 0;
  const numeric = Number(trimmed);
  return Number.isFinite(numeric) ? numeric : 0;
}

/**
 * Wizard para registrar el pago de una cuota de deuda (PHASE-22).
 * Espejo de `apps/web/components/accounts/debt-payment-wizard.tsx`.
 *
 * Crea:
 * 1. Una transacción `expense` en la cuenta origen con la categoría de
 *    intereses correspondiente — sólo si el split de intereses > 0.
 * 2. Una transferencia interna que mueve el principal de la cuenta
 *    origen a la liability: dos transacciones sin categoría enlazadas
 *    vía `useLinkTransfer`. Esto reduce el saldo de la cuenta origen
 *    y reduce el saldo de la liability (porque para liabilities el
 *    sign está invertido en el backend).
 *
 * Si la liability tiene cuadro de amortización y la fecha actual cae
 * dentro del calendario, el split se precarga con los valores teóricos
 * del mes en curso.
 */
export function DebtPaymentWizard({
  liabilityAccount,
  visible,
  onClose,
}: DebtPaymentWizardProps) {
  const accountsQuery = useAccounts();
  const categoriesQuery = useCategories();
  // Amortización opcional: si la cuenta no tiene los datos, el query
  // devolverá 400 y dejamos `rows = []`.
  const scheduleQuery = useAmortizationSchedule(liabilityAccount.id);

  const principalTxMutation = useCreateTransaction();
  const liabilityTxMutation = useCreateTransaction();
  const interestTxMutation = useCreateTransaction();
  const linkMutation = useLinkTransfer();

  const accounts = accountsQuery.data ?? [];
  const categories = categoriesQuery.data ?? [];

  // Sólo cuentas asset activas en la misma moneda que la liability.
  const sourceAccounts = useMemo(
    () =>
      accounts.filter(
        (a) =>
          !a.is_archived &&
          ASSET_ACCOUNT_TYPES.includes(a.type) &&
          a.currency === liabilityAccount.currency,
      ),
    [accounts, liabilityAccount.currency],
  );

  const interestCategoryName = INTEREST_CATEGORY_BY_TYPE[liabilityAccount.type];
  const interestCategory = categories.find(
    (c) => c.kind === 'expense' && c.name === interestCategoryName,
  );

  const currentMonthRow = useMemo(() => {
    if (!scheduleQuery.data) return undefined;
    return findCurrentMonthRow(scheduleQuery.data.rows);
  }, [scheduleQuery.data]);

  const [sourceAccountId, setSourceAccountId] = useState<string>('');
  const [totalAmount, setTotalAmount] = useState<string>('');
  const [principalAmount, setPrincipalAmount] = useState<string>('');
  const [interestAmount, setInterestAmount] = useState<string>('');
  const [categoryId, setCategoryId] = useState<string>('');
  const [occurredAt, setOccurredAt] = useState<string>(
    toDateInputValue(new Date().toISOString()),
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // El usuario marca qué campo controla: cuando edita "principal", el
  // "interest" se recalcula como total - principal, y viceversa.
  const [lastEdited, setLastEdited] = useState<'principal' | 'interest'>(
    'principal',
  );

  // Cuando se abre el wizard, precargamos:
  // - Cuenta origen: primera asset disponible
  // - Total: cuota del mes actual del cuadro o vacío
  // - Split: principal/interest del cuadro o 100% principal
  // - Categoría: la de intereses del tipo de liability
  // - Fecha: hoy
  useEffect(() => {
    if (!visible) return;
    if (sourceAccounts[0] && !sourceAccountId) {
      setSourceAccountId(sourceAccounts[0].id);
    }
    if (interestCategory && !categoryId) {
      setCategoryId(interestCategory.id);
    }
    if (currentMonthRow && !totalAmount) {
      setTotalAmount(currentMonthRow.payment);
      setPrincipalAmount(currentMonthRow.principal);
      setInterestAmount(currentMonthRow.interest);
    }
    // Las deps son intencionales: queremos correr el bootstrap una vez
    // al abrir o cuando llegan los datos necesarios. No reaccionamos a
    // cambios posteriores del propio usuario (los guards `&& !state`
    // ya cortan re-fills indeseados, y deliberadamente NO se incluyen
    // `totalAmount` ni `categoryId` para no resetear lo que el
    // usuario está editando).
  }, [visible, sourceAccounts.length, interestCategory?.id, currentMonthRow?.payment]);

  /**
   * Cuando cambia el total y nada más, repartimos manteniendo la
   * proporción del último split conocido si era no trivial; si no,
   * vamos 100% principal por simplicidad.
   */
  function handleTotalChange(next: string) {
    setTotalAmount(next);
    const totalNum = parseAmount(next);
    if (totalNum <= 0) {
      setPrincipalAmount('');
      setInterestAmount('');
      return;
    }
    const prevPrincipal = parseAmount(principalAmount);
    const prevInterest = parseAmount(interestAmount);
    const prevTotal = prevPrincipal + prevInterest;
    if (prevTotal > 0) {
      const ratio = prevPrincipal / prevTotal;
      const newPrincipal = (totalNum * ratio).toFixed(2);
      const newInterest = (totalNum - Number(newPrincipal)).toFixed(2);
      setPrincipalAmount(newPrincipal);
      setInterestAmount(newInterest);
    } else {
      setPrincipalAmount(totalNum.toFixed(2));
      setInterestAmount('0.00');
    }
  }

  function handlePrincipalChange(next: string) {
    setPrincipalAmount(next);
    setLastEdited('principal');
    const totalNum = parseAmount(totalAmount);
    const principalNum = parseAmount(next);
    if (totalNum > 0) {
      const remainder = Math.max(0, totalNum - principalNum);
      setInterestAmount(remainder.toFixed(2));
    }
  }

  function handleInterestChange(next: string) {
    setInterestAmount(next);
    setLastEdited('interest');
    const totalNum = parseAmount(totalAmount);
    const interestNum = parseAmount(next);
    if (totalNum > 0) {
      const remainder = Math.max(0, totalNum - interestNum);
      setPrincipalAmount(remainder.toFixed(2));
    }
  }

  function reset() {
    setSourceAccountId('');
    setTotalAmount('');
    setPrincipalAmount('');
    setInterestAmount('');
    setCategoryId('');
    setOccurredAt(toDateInputValue(new Date().toISOString()));
    setError(null);
    setLastEdited('principal');
  }

  function handleClose() {
    if (submitting) return;
    reset();
    onClose();
  }

  async function handleSubmit() {
    setError(null);
    const totalNum = parseAmount(totalAmount);
    const principalNum = parseAmount(principalAmount);
    const interestNum = parseAmount(interestAmount);

    if (!sourceAccountId) {
      setError('Selecciona la cuenta origen.');
      return;
    }
    if (totalNum <= 0) {
      setError('El importe total debe ser mayor que 0.');
      return;
    }
    // Permitimos 1 céntimo de holgura por redondeo.
    if (Math.abs(principalNum + interestNum - totalNum) > 0.01) {
      setError('El reparto principal + intereses debe sumar el total.');
      return;
    }
    if (principalNum < 0 || interestNum < 0) {
      setError('Los importes no pueden ser negativos.');
      return;
    }
    if (interestNum > 0 && !categoryId) {
      setError('Selecciona la categoría para los intereses.');
      return;
    }

    setSubmitting(true);
    try {
      const occurredAtIso = fromDateInputValue(occurredAt);
      const currency = liabilityAccount.currency;

      // 1. Crear la transferencia: expense en cuenta origen +
      //    income en liability (sin categoría), luego enlazar.
      if (principalNum > 0) {
        const outTx = await principalTxMutation.mutateAsync({
          account_id: sourceAccountId,
          amount: principalNum.toFixed(2),
          currency,
          occurred_at: occurredAtIso,
          description: `Pago a ${liabilityAccount.name} (principal)`,
          category_id: null,
        });
        const inTx = await liabilityTxMutation.mutateAsync({
          account_id: liabilityAccount.id,
          amount: principalNum.toFixed(2),
          currency,
          occurred_at: occurredAtIso,
          description: `Amortización ${liabilityAccount.name}`,
          category_id: null,
        });
        await linkMutation.mutateAsync({
          out_transaction_id: outTx.id,
          in_transaction_id: inTx.id,
        });
      }

      // 2. Crear la expense de intereses sobre la cuenta origen.
      if (interestNum > 0) {
        await interestTxMutation.mutateAsync({
          account_id: sourceAccountId,
          amount: interestNum.toFixed(2),
          currency,
          occurred_at: occurredAtIso,
          description: `Intereses ${liabilityAccount.name}`,
          category_id: categoryId || null,
        });
      }

      toast.success('Cuota registrada.');
      reset();
      onClose();
    } catch (err) {
      const message = formatApiError(err, 'Error al registrar la cuota.');
      setError(message);
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  const expenseCategories = categories.filter((c) => c.kind === 'expense');
  const interestDisabled = parseAmount(interestAmount) <= 0;

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent
      onRequestClose={handleClose}
    >
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <View style={styles.header}>
            <View style={{ flex: 1, minWidth: 0 }}>
              <Text style={styles.title}>Pagar cuota</Text>
              <Text style={styles.subtitle} numberOfLines={2}>
                <Text style={styles.subtitleStrong}>
                  {liabilityAccount.name}
                </Text>
                {' · El principal se mueve como transferencia interna y los intereses se registran como gasto.'}
                {currentMonthRow
                  ? ' Precargado desde el cuadro francés del mes actual.'
                  : ''}
              </Text>
            </View>
            <Pressable onPress={handleClose} accessibilityRole="button">
              <Text style={styles.closeText}>✕</Text>
            </Pressable>
          </View>

          <ScrollView contentContainerStyle={styles.content}>
            <View>
              <Text style={styles.label}>Cuenta origen</Text>
              {sourceAccounts.length === 0 ? (
                <Text style={styles.warning}>
                  No tienes cuentas asset en {liabilityAccount.currency} para
                  pagar esta deuda.
                </Text>
              ) : (
                <View style={styles.chipGrid}>
                  {sourceAccounts.map((a) => {
                    const selected = a.id === sourceAccountId;
                    return (
                      <Pressable
                        key={a.id}
                        onPress={() => setSourceAccountId(a.id)}
                        style={[styles.chip, selected && styles.chipActive]}
                      >
                        <Text
                          style={[
                            styles.chipText,
                            selected && styles.chipTextActive,
                          ]}
                        >
                          {a.icon ? `${a.icon} ` : ''}
                          {a.name} ({a.currency})
                        </Text>
                      </Pressable>
                    );
                  })}
                </View>
              )}
            </View>

            <View>
              <Text style={styles.label}>Importe total</Text>
              <TextInput
                style={styles.input}
                value={totalAmount}
                onChangeText={handleTotalChange}
                keyboardType="decimal-pad"
                placeholder="0.00"
                placeholderTextColor={colors.textMuted}
              />
            </View>

            <View style={styles.splitRow}>
              <View style={styles.splitCell}>
                <Text style={styles.label}>Principal</Text>
                <TextInput
                  style={styles.input}
                  value={principalAmount}
                  onChangeText={handlePrincipalChange}
                  keyboardType="decimal-pad"
                  placeholder="0.00"
                  placeholderTextColor={colors.textMuted}
                />
              </View>
              <View style={styles.splitCell}>
                <Text style={styles.label}>Intereses</Text>
                <TextInput
                  style={styles.input}
                  value={interestAmount}
                  onChangeText={handleInterestChange}
                  keyboardType="decimal-pad"
                  placeholder="0.00"
                  placeholderTextColor={colors.textMuted}
                />
              </View>
            </View>

            <Text style={styles.splitHelp}>
              Reparto:{' '}
              {formatAmount(principalAmount || '0', liabilityAccount.currency)}{' '}
              principal +{' '}
              {formatAmount(interestAmount || '0', liabilityAccount.currency)}{' '}
              intereses
              {lastEdited === 'interest'
                ? ' · Principal se ajusta al cambiar intereses.'
                : ''}
            </Text>

            <View>
              <Text style={styles.label}>Categoría de intereses</Text>
              <View style={styles.chipGrid}>
                <Pressable
                  onPress={() => setCategoryId('')}
                  disabled={interestDisabled}
                  style={[
                    styles.chip,
                    categoryId === '' && styles.chipActive,
                    interestDisabled && styles.chipDisabled,
                  ]}
                >
                  <Text
                    style={[
                      styles.chipText,
                      categoryId === '' && styles.chipTextActive,
                    ]}
                  >
                    Sin categoría
                  </Text>
                </Pressable>
                {expenseCategories.map((c) => {
                  const selected = c.id === categoryId;
                  return (
                    <Pressable
                      key={c.id}
                      onPress={() => setCategoryId(c.id)}
                      disabled={interestDisabled}
                      style={[
                        styles.chip,
                        selected && styles.chipActive,
                        interestDisabled && styles.chipDisabled,
                      ]}
                    >
                      <Text
                        style={[
                          styles.chipText,
                          selected && styles.chipTextActive,
                        ]}
                      >
                        {c.icon ? `${c.icon} ` : ''}
                        {c.name}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            </View>

            <DateInput
              label="Fecha"
              value={occurredAt}
              onChange={setOccurredAt}
            />

            {error ? (
              <View style={styles.errorBox}>
                <Text style={styles.errorText}>{error}</Text>
              </View>
            ) : null}
          </ScrollView>

          <View style={styles.actions}>
            <Pressable
              onPress={handleClose}
              disabled={submitting}
              style={styles.actionGhost}
            >
              <Text style={styles.actionGhostText}>Cancelar</Text>
            </Pressable>
            <Pressable
              onPress={() => {
                void handleSubmit();
              }}
              disabled={submitting || sourceAccounts.length === 0}
              style={[
                styles.actionPrimary,
                (submitting || sourceAccounts.length === 0) &&
                  styles.actionPrimaryDisabled,
              ]}
            >
              <Text style={styles.actionPrimaryText}>
                {submitting ? 'Registrando…' : 'Pagar cuota'}
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
    alignItems: 'flex-start',
    gap: spacing.sm,
    padding: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  title: {
    fontSize: fontSize.lg,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  subtitle: {
    marginTop: spacing.xs,
    fontSize: fontSize.xs,
    color: colors.textMuted,
    lineHeight: 16,
  },
  subtitleStrong: {
    color: colors.text,
    fontWeight: fontWeight.semibold,
  },
  closeText: { fontSize: fontSize.lg, color: colors.textMuted },
  content: {
    padding: spacing.md,
    gap: spacing.md,
    paddingBottom: spacing.lg,
  },
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
  warning: {
    color: colors.warning,
    fontSize: fontSize.xs,
    lineHeight: 16,
  },
  chipGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
  },
  chip: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  chipActive: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primary,
  },
  chipDisabled: { opacity: 0.5 },
  chipText: {
    fontSize: fontSize.sm,
    color: colors.text,
    fontWeight: fontWeight.medium,
  },
  chipTextActive: {
    color: colors.primary,
    fontWeight: fontWeight.semibold,
  },
  splitRow: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  splitCell: {
    flex: 1,
  },
  splitHelp: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    lineHeight: 16,
    marginTop: -spacing.xs,
  },
  errorBox: {
    backgroundColor: colors.dangerSoft,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  errorText: {
    color: colors.danger,
    fontSize: fontSize.sm,
  },
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
