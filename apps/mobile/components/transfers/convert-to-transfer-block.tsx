import { useEffect, useRef, useState } from 'react';
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
 * PHASE-23.1 / P7 (transfers-ux) — bloque "Convertir en transferencia"
 * en mobile. El usuario DECLARA la dirección (salió/entró) con un toggle
 * explícito + elige la otra cuenta. Antes la dirección se infería de
 * `category.kind`, así que un bank-mapping equivocado invertía el saldo
 * sin que el usuario pudiera corregirlo (el bug de signo de PHASE-28,
 * que el web ya cerró con dos slots). El `kind` sólo da la SUGERENCIA
 * inicial del toggle, editable.
 */
export function ConvertToTransferBlock({ transaction, onConverted, onError }: Props) {
  const accountsQuery = useAccounts({ includeArchived: false });
  const categoriesQuery = useCategories();
  const mutation = useConvertToTransfer();
  const [otherAccountId, setOtherAccountId] = useState<string | null>(null);
  const [direction, setDirection] = useState<Direction>('outgoing');
  // El usuario manda: una vez toca el toggle, no lo pisa la sugerencia.
  const userPickedDirection = useRef(false);

  const accounts = accountsQuery.data ?? [];
  const candidates = accounts.filter(
    (a) =>
      a.id !== transaction.account_id &&
      a.currency === transaction.currency &&
      !a.is_archived,
  );

  const ownName =
    accounts.find((a) => a.id === transaction.account_id)?.name ?? 'esta cuenta';
  const category = (categoriesQuery.data ?? []).find(
    (c) => c.id === transaction.category_id,
  );

  // Sugerencia inicial desde el kind (editable). Se ajusta cuando las
  // categorías cargan, salvo que el usuario ya haya elegido a mano.
  useEffect(() => {
    if (userPickedDirection.current) return;
    if (category?.kind === 'income') setDirection('incoming');
    else if (category?.kind === 'expense') setDirection('outgoing');
  }, [category?.kind]);

  function pickDirection(next: Direction) {
    userPickedDirection.current = true;
    setDirection(next);
  }

  const otherAccountLabel =
    direction === 'incoming' ? '¿De qué cuenta salió?' : '¿A qué cuenta entró?';

  function handleSubmit() {
    if (!otherAccountId) return;
    // Dirección DECLARADA por el usuario (no inferida):
    //   - "salió de esta cuenta" → la cuenta de la tx es ordenante.
    //   - "entró en esta cuenta" → la cuenta de la tx es beneficiaria.
    const originatingAccountId =
      direction === 'incoming' ? otherAccountId : transaction.account_id;
    const beneficiaryAccountId =
      direction === 'incoming' ? transaction.account_id : otherAccountId;
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
      <Text style={styles.hint}>
        Dinos si el dinero salió de {ownName} o entró en {ownName}. Crearemos la
        contraparte y ambos saldos reflejarán el movimiento.
      </Text>

      <Text style={styles.fieldLabel}>¿Qué pasó en {ownName}?</Text>
      <View style={styles.options}>
        <Pressable
          onPress={() => pickDirection('outgoing')}
          style={[styles.option, direction === 'outgoing' && styles.optionSelected]}
        >
          <Text
            style={[
              styles.optionText,
              direction === 'outgoing' && styles.optionTextSelected,
            ]}
          >
            Salió de aquí
          </Text>
        </Pressable>
        <Pressable
          onPress={() => pickDirection('incoming')}
          style={[styles.option, direction === 'incoming' && styles.optionSelected]}
        >
          <Text
            style={[
              styles.optionText,
              direction === 'incoming' && styles.optionTextSelected,
            ]}
          >
            Entró aquí
          </Text>
        </Pressable>
      </View>

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
              const selected = acc.id === otherAccountId;
              return (
                <Pressable
                  key={acc.id}
                  onPress={() => setOtherAccountId(acc.id)}
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
            disabled={!otherAccountId || mutation.isPending}
            style={({ pressed }) => [
              styles.cta,
              (pressed || mutation.isPending || !otherAccountId) && {
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
