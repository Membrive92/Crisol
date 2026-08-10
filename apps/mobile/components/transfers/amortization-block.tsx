import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import {
  useAccounts,
  useAmortization,
  useAmortize,
  usePreviewAmortization,
  useUndoAmortization,
} from '@crisol/services';
import type { AmortizationEffect, Transaction } from '@crisol/types';
import {
  amortizationChoiceHint,
  amortizationChoiceLabel,
  amortizationEffectCopy,
  amortizationRegisteredCopy,
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
} from '@crisol/ui';

interface Props {
  transaction: Transaction;
  onRegistered: (effect: AmortizationEffect) => void;
  onUndone: () => void;
  onError: (err: unknown) => void;
}

/**
 * PHASE-45 — bloque "¿Es una amortización?" en móvil.
 *
 * Paridad con el panel de web: mismas frases (todas salen de `@crisol/ui`),
 * mismo previsualizador contra el servidor y misma decisión explícita de si el
 * pago cuenta como gasto. Sólo cambia el renderizado.
 */
export function AmortizationBlock({
  transaction,
  onRegistered,
  onUndone,
  onError,
}: Props) {
  const accountsQuery = useAccounts({ includeArchived: false });
  const stateQuery = useAmortization(transaction.id);
  const preview = usePreviewAmortization();
  const amortize = useAmortize();
  const undo = useUndoAmortization();

  const [liabilityId, setLiabilityId] = useState<string | null>(null);
  const [countsAsExpense, setCountsAsExpense] = useState<boolean | null>(null);
  const [effect, setEffect] = useState<AmortizationEffect | null>(null);

  const liabilities = (accountsQuery.data ?? []).filter(
    (a) =>
      a.nature === 'liability' &&
      !a.is_archived &&
      a.currency === transaction.currency &&
      a.id !== transaction.account_id,
  );

  useEffect(() => {
    if (!liabilityId) {
      setEffect(null);
      return;
    }
    let cancelled = false;
    preview.mutate(
      {
        source_transaction_id: transaction.id,
        liability_account_id: liabilityId,
      },
      {
        onSuccess: (result) => {
          if (cancelled) return;
          setEffect(result);
          setCountsAsExpense(result.suggested_counts_as_expense);
        },
        onError: (err) => {
          if (cancelled) return;
          setEffect(null);
          onError(err);
        },
      },
    );
    return () => {
      cancelled = true;
    };
    // Sólo reaccionamos a la deuda elegida; `preview` es estable.
  }, [liabilityId, transaction.id]);

  const registered = stateQuery.data ?? null;

  function handleSubmit() {
    if (!liabilityId || countsAsExpense === null) return;
    amortize.mutate(
      {
        source_transaction_id: transaction.id,
        liability_account_id: liabilityId,
        counts_as_expense: countsAsExpense,
      },
      {
        onSuccess: (result) => {
          setLiabilityId(null);
          setEffect(null);
          onRegistered(result);
        },
        onError: (err) => onError(err),
      },
    );
  }

  if (stateQuery.isLoading) {
    return (
      <View style={styles.card}>
        <Text style={styles.title}>¿Es una amortización?</Text>
        <Text style={styles.hint}>Comprobando…</Text>
      </View>
    );
  }

  if (registered) {
    return (
      <View style={styles.card}>
        <Text style={styles.title}>¿Es una amortización?</Text>
        <Text style={styles.hint}>
          {amortizationRegisteredCopy({
            mode: registered.mode,
            installmentsMarked: registered.installments_marked,
            liabilityName: registered.liability_account_name,
          })}
        </Text>
        <Text style={styles.fact}>
          Capital amortizado:{' '}
          {formatAmount(registered.principal_covered, registered.currency)} · Deuda ahora:{' '}
          {formatAmount(registered.outstanding_after, registered.currency)} · Cuenta como
          gasto: {registered.counts_as_expense ? 'Sí' : 'No'}
        </Text>
        <Pressable
          onPress={() =>
            undo.mutate(transaction.id, {
              onSuccess: () => onUndone(),
              onError: (err) => onError(err),
            })
          }
          disabled={undo.isPending}
          style={({ pressed }) => [
            styles.secondaryCta,
            (pressed || undo.isPending) && { opacity: 0.6 },
          ]}
        >
          <Text style={styles.secondaryCtaText}>
            {undo.isPending ? 'Deshaciendo…' : 'Deshacer registro'}
          </Text>
        </Pressable>
      </View>
    );
  }

  const copy = effect
    ? amortizationEffectCopy({
        mode: effect.mode,
        installmentsMarked: effect.installments_marked,
        liabilityName: effect.liability_account_name,
        principalCovered: effect.principal_covered,
        outstandingBefore: effect.outstanding_before,
        outstandingAfter: effect.outstanding_after,
        currency: effect.currency,
      })
    : null;

  return (
    <View style={styles.card}>
      <Text style={styles.title}>¿Es una amortización?</Text>
      {liabilities.length === 0 ? (
        <Text style={styles.empty}>
          No tienes cuentas de deuda en {transaction.currency} distintas de la de este
          movimiento.
        </Text>
      ) : (
        <>
          <Text style={styles.hint}>
            Si este cargo paga una deuda tuya, dilo aquí y la deuda bajará.
          </Text>
          <Text style={styles.fieldLabel}>¿Qué deuda amortiza?</Text>
          <View style={styles.options}>
            {liabilities.map((acc) => {
              const selected = acc.id === liabilityId;
              return (
                <Pressable
                  key={acc.id}
                  onPress={() => setLiabilityId(acc.id)}
                  style={[styles.option, selected && styles.optionSelected]}
                >
                  <Text style={[styles.optionText, selected && styles.optionTextSelected]}>
                    {acc.name}
                  </Text>
                </Pressable>
              );
            })}
          </View>

          {preview.isPending ? <Text style={styles.hint}>Calculando el efecto…</Text> : null}

          {effect && copy ? (
            <>
              <View style={styles.effectBox}>
                <Text style={copy.tone === 'warning' ? styles.warn : styles.effectText}>
                  {copy.headline}
                </Text>
                <Text style={styles.effectText}>{copy.balanceLine}</Text>
              </View>

              <Text style={styles.fieldLabel}>¿Cuenta como gasto?</Text>
              <View style={styles.options}>
                {[true, false].map((option) => {
                  const selected = countsAsExpense === option;
                  return (
                    <Pressable
                      key={String(option)}
                      onPress={() => setCountsAsExpense(option)}
                      style={[styles.option, selected && styles.optionSelected]}
                    >
                      <Text
                        style={[styles.optionText, selected && styles.optionTextSelected]}
                      >
                        {amortizationChoiceLabel(option)}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
              <Text style={styles.reason}>
                {amortizationChoiceHint(
                  countsAsExpense,
                  effect.suggested_counts_as_expense,
                  effect.suggestion_reason,
                )}
              </Text>

              <Pressable
                onPress={handleSubmit}
                disabled={amortize.isPending || countsAsExpense === null}
                style={({ pressed }) => [
                  styles.cta,
                  (pressed || amortize.isPending || countsAsExpense === null) && {
                    opacity: 0.6,
                  },
                ]}
              >
                <Text style={styles.ctaText}>
                  {amortize.isPending ? 'Registrando…' : 'Registrar amortización'}
                </Text>
              </Pressable>
            </>
          ) : null}
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
    marginTop: spacing.md,
  },
  title: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
    marginBottom: spacing.xs,
  },
  hint: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    marginBottom: spacing.sm,
    lineHeight: 18,
  },
  fact: {
    fontSize: fontSize.sm,
    color: colors.text,
    marginBottom: spacing.sm,
    lineHeight: 18,
  },
  fieldLabel: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    color: colors.text,
    marginBottom: spacing.xs,
  },
  empty: {
    fontSize: fontSize.sm,
    color: colors.textSubtle,
    fontStyle: 'italic',
  },
  options: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
    marginBottom: spacing.sm,
  },
  option: {
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  optionSelected: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primary,
  },
  optionText: {
    fontSize: fontSize.sm,
    color: colors.text,
  },
  optionTextSelected: {
    color: colors.primary,
    fontWeight: fontWeight.semibold,
  },
  effectBox: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.sm,
    padding: spacing.sm,
    marginBottom: spacing.sm,
    gap: spacing.xs,
  },
  effectText: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    lineHeight: 18,
  },
  warn: {
    fontSize: fontSize.sm,
    color: colors.warning,
    lineHeight: 18,
  },
  reason: {
    fontSize: fontSize.xs,
    color: colors.textSubtle,
    lineHeight: 16,
    marginBottom: spacing.sm,
  },
  cta: {
    alignSelf: 'flex-start',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.primary,
  },
  ctaText: {
    color: colors.onPrimary,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
  },
  secondaryCta: {
    alignSelf: 'flex-start',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  secondaryCtaText: {
    color: colors.text,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
  },
});
