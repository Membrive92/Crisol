import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import {
  useAccounts,
  useCategories,
  useConvertToTransfer,
} from '@crisol/services';
import type { Transaction, TransferPair } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

interface Props {
  transaction: Transaction;
  onConverted: (pair: TransferPair) => void;
  onError: (err: unknown) => void;
}

type Direction = 'outgoing' | 'incoming';

/**
 * PHASE-23.1 — bloque "Convertir en transferencia" en mobile. Mismo
 * comportamiento que el dialog web: lista cuentas elegibles (misma
 * moneda, distinta a la origen, no archivadas) y dispara
 * `POST /transfers/from-source`.
 */
export function ConvertToTransferBlock({ transaction, onConverted, onError }: Props) {
  const accountsQuery = useAccounts({ includeArchived: false });
  const categoriesQuery = useCategories();
  const mutation = useConvertToTransfer();
  const [destinationId, setDestinationId] = useState<string | null>(null);

  const accounts = accountsQuery.data ?? [];
  const candidates = accounts.filter(
    (a) =>
      a.id !== transaction.account_id &&
      a.currency === transaction.currency &&
      !a.is_archived,
  );

  const category = (categoriesQuery.data ?? []).find(
    (c) => c.id === transaction.category_id,
  );
  const direction: Direction =
    category?.kind === 'income' ? 'incoming' : 'outgoing';
  const otherAccountLabel =
    direction === 'incoming' ? 'Cuenta origen' : 'Cuenta destino';
  const hint =
    direction === 'incoming'
      ? `Si este ingreso vino de otra de tus cuentas, elige cuál. Se creará la salida correspondiente y ambos saldos reflejarán el movimiento.`
      : `Si esta salida fue hacia otra de tus cuentas, elige cuál. Se creará la entrada correspondiente y ambos saldos reflejarán el movimiento.`;

  function handleSubmit() {
    if (!destinationId) return;
    // Mapeo a la API explícita ordenante/beneficiaria:
    //   - tx con categoría INCOME → la cuenta de la tx es beneficiaria,
    //     la otra (destinationId) es ordenante.
    //   - en cualquier otro caso (expense/null) → la cuenta de la tx
    //     es ordenante, la otra es beneficiaria.
    // Este mobile mantiene la inferencia desde categoría como antes;
    // el web ya expone los dos slots al usuario explícitamente.
    const originatingAccountId =
      direction === 'incoming' ? destinationId : transaction.account_id;
    const beneficiaryAccountId =
      direction === 'incoming' ? transaction.account_id : destinationId;
    mutation.mutate(
      {
        source_transaction_id: transaction.id,
        originating_account_id: originatingAccountId,
        beneficiary_account_id: beneficiaryAccountId,
      },
      {
        onSuccess: (pair) => onConverted(pair),
        onError: (err) => onError(err),
      },
    );
  }

  return (
    <View style={styles.card}>
      <Text style={styles.title}>¿Es un movimiento entre tus cuentas?</Text>
      <Text style={styles.hint}>{hint}</Text>
      <Text style={styles.fieldLabel}>{otherAccountLabel}</Text>
      {candidates.length === 0 ? (
        <Text style={styles.empty}>
          No tienes otras cuentas activas en {transaction.currency}. Crea
          una en Ajustes para poder convertir esta tx.
        </Text>
      ) : (
        <>
          <View style={styles.options}>
            {candidates.map((acc) => {
              const selected = acc.id === destinationId;
              return (
                <Pressable
                  key={acc.id}
                  onPress={() => setDestinationId(acc.id)}
                  style={[styles.option, selected && styles.optionSelected]}
                >
                  <Text
                    style={[
                      styles.optionText,
                      selected && styles.optionTextSelected,
                    ]}
                  >
                    {acc.name}
                  </Text>
                </Pressable>
              );
            })}
          </View>
          <Pressable
            onPress={handleSubmit}
            disabled={!destinationId || mutation.isPending}
            style={({ pressed }) => [
              styles.cta,
              (pressed || mutation.isPending || !destinationId) && {
                opacity: 0.6,
              },
            ]}
          >
            <Text style={styles.ctaText}>
              {mutation.isPending
                ? 'Convirtiendo…'
                : 'Convertir en transferencia'}
            </Text>
          </Pressable>
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
});
