import { useMemo, useState } from 'react';
import {
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { useAccounts, useConvertToDebt } from '@crisol/services';
import type {
  NewLiabilityForDebt,
  Transaction,
  TransferPair,
} from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

interface Props {
  transaction: Transaction;
  /** P2 (transfers-ux): la heurística ya no oculta el bloque; sólo lo
   * destaca con un chip "Sugerido". */
  suggested?: boolean;
  onConverted: (pair: TransferPair) => void;
  onError: (err: unknown) => void;
}

type Mode = 'existing' | 'new';
type LiabilityType = NewLiabilityForDebt['type'];

const LIABILITY_TYPE_LABEL: Record<LiabilityType, string> = {
  credit_card: 'Tarjeta',
  loan: 'Préstamo/Financiada',
  mortgage: 'Hipoteca',
};

/**
 * PHASE-24 — equivalente mobile de ConvertToDebtDialog.
 * Mismo flujo: usar liability existente o crear nueva al vuelo.
 */
export function ConvertToDebtBlock({
  transaction,
  suggested,
  onConverted,
  onError,
}: Props) {
  const accountsQuery = useAccounts({ includeArchived: false });
  const mutation = useConvertToDebt();

  const liabilities = useMemo(
    () =>
      (accountsQuery.data ?? []).filter(
        (a) =>
          a.nature === 'liability' &&
          a.currency === transaction.currency &&
          !a.is_archived,
      ),
    [accountsQuery.data, transaction.currency],
  );

  const [mode, setMode] = useState<Mode>(
    liabilities.length > 0 ? 'existing' : 'new',
  );
  const [destinationId, setDestinationId] = useState<string | null>(null);
  const [name, setName] = useState<string>('Compra financiada');
  const [type, setType] = useState<LiabilityType>('loan');
  const [aprPercent, setAprPercent] = useState<string>('');
  const [taePercent, setTaePercent] = useState<string>('');
  const [termMonths, setTermMonths] = useState<string>('');
  const [totalToPay, setTotalToPay] = useState<string>('');
  // PHASE-24.2: cualquier tipo de deuda acepta plan fijo.
  const acceptsAmortization = true;

  function handleSubmit() {
    if (mode === 'existing') {
      if (!destinationId) return;
      mutation.mutate(
        {
          source_transaction_id: transaction.id,
          destination_account_id: destinationId,
        },
        { onSuccess: onConverted, onError },
      );
      return;
    }
    if (!name.trim()) return;
    const newLiability: NewLiabilityForDebt = {
      name: name.trim(),
      type,
      currency: transaction.currency,
    };
    if (acceptsAmortization) {
      const aprTrimmed = aprPercent.trim().replace(',', '.');
      if (aprTrimmed) {
        const aprNumeric = Number(aprTrimmed);
        if (Number.isFinite(aprNumeric)) {
          newLiability.apr = (aprNumeric / 100).toFixed(4);
        }
      }
      const taeTrimmed = taePercent.trim().replace(',', '.');
      if (taeTrimmed) {
        const taeNumeric = Number(taeTrimmed);
        if (Number.isFinite(taeNumeric)) {
          newLiability.tae = (taeNumeric / 100).toFixed(4);
        }
      }
      const term = termMonths.trim();
      if (term) {
        const n = Number(term);
        if (Number.isFinite(n) && n > 0) newLiability.term_months = n;
      }
      const totalRaw = totalToPay.trim().replace(',', '.');
      if (totalRaw) newLiability.total_to_pay = totalRaw;
    }
    mutation.mutate(
      {
        source_transaction_id: transaction.id,
        new_liability: newLiability,
      },
      { onSuccess: onConverted, onError },
    );
  }

  return (
    <View style={styles.card}>
      <View style={styles.titleRow}>
        <Text style={styles.title}>¿Es una operación financiada?</Text>
        {suggested ? (
          <View style={styles.suggestedChip}>
            <Text style={styles.suggestedChipText}>Sugerido</Text>
          </View>
        ) : null}
      </View>
      <Text style={styles.hint}>
        Si el banco te abonó este importe como compra a plazos o préstamo,
        regístralo como deuda. Se creará la contraparte y la deuda crecerá
        por {transaction.amount} {transaction.currency}.
      </Text>

      <View style={styles.tabs}>
        <Pressable
          onPress={() =>
            liabilities.length > 0 ? setMode('existing') : null
          }
          disabled={liabilities.length === 0}
          style={[
            styles.tab,
            mode === 'existing' && styles.tabActive,
            liabilities.length === 0 && { opacity: 0.4 },
          ]}
        >
          <Text
            style={[styles.tabText, mode === 'existing' && styles.tabTextActive]}
          >
            Usar deuda existente
          </Text>
        </Pressable>
        <Pressable
          onPress={() => setMode('new')}
          style={[styles.tab, mode === 'new' && styles.tabActive]}
        >
          <Text
            style={[styles.tabText, mode === 'new' && styles.tabTextActive]}
          >
            Crear nueva
          </Text>
        </Pressable>
      </View>

      {mode === 'existing' ? (
        liabilities.length === 0 ? (
          <Text style={styles.empty}>
            No tienes cuentas de deuda en {transaction.currency}. Pulsa
            "Crear nueva" para registrar una.
          </Text>
        ) : (
          <>
            <View style={styles.chips}>
              {liabilities.map((acc) => {
                const selected = acc.id === destinationId;
                return (
                  <Pressable
                    key={acc.id}
                    onPress={() => setDestinationId(acc.id)}
                    style={[styles.chip, selected && styles.chipSelected]}
                  >
                    <Text
                      style={[
                        styles.chipText,
                        selected && styles.chipTextSelected,
                      ]}
                    >
                      {acc.name} ·{' '}
                      {LIABILITY_TYPE_LABEL[acc.type as LiabilityType] ?? acc.type}
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
                {mutation.isPending ? 'Registrando…' : 'Registrar como deuda'}
              </Text>
            </Pressable>
          </>
        )
      ) : (
        <>
          <Text style={styles.fieldLabel}>Nombre</Text>
          <TextInput
            style={styles.input}
            value={name}
            onChangeText={setName}
            maxLength={100}
            placeholder="Tarjeta financiada BBVA"
            placeholderTextColor={colors.textMuted}
          />
          <Text style={styles.fieldLabel}>Tipo</Text>
          <View style={styles.chips}>
            {(['loan', 'mortgage', 'credit_card'] as const).map((t) => {
              const selected = t === type;
              return (
                <Pressable
                  key={t}
                  onPress={() => setType(t)}
                  style={[styles.chip, selected && styles.chipSelected]}
                >
                  <Text
                    style={[
                      styles.chipText,
                      selected && styles.chipTextSelected,
                    ]}
                  >
                    {LIABILITY_TYPE_LABEL[t]}
                  </Text>
                </Pressable>
              );
            })}
          </View>
          {acceptsAmortization ? (
            <>
              <View style={styles.row}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.fieldLabel}>TIN (%)</Text>
                  <TextInput
                    style={styles.input}
                    value={aprPercent}
                    onChangeText={setAprPercent}
                    placeholder="5,90"
                    placeholderTextColor={colors.textMuted}
                    keyboardType="decimal-pad"
                  />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.fieldLabel}>TAE (%) opc.</Text>
                  <TextInput
                    style={styles.input}
                    value={taePercent}
                    onChangeText={setTaePercent}
                    placeholder="6,12"
                    placeholderTextColor={colors.textMuted}
                    keyboardType="decimal-pad"
                  />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.fieldLabel}>Plazo (m)</Text>
                  <TextInput
                    style={styles.input}
                    value={termMonths}
                    onChangeText={setTermMonths}
                    placeholder="12"
                    placeholderTextColor={colors.textMuted}
                    keyboardType="number-pad"
                  />
                </View>
              </View>
              <Text style={styles.fieldLabel}>Total a pagar (€) opc.</Text>
              <TextInput
                style={styles.input}
                value={totalToPay}
                onChangeText={setTotalToPay}
                placeholder="913,86"
                placeholderTextColor={colors.textMuted}
                keyboardType="decimal-pad"
              />
            </>
          ) : null}
          <Pressable
            onPress={handleSubmit}
            disabled={!name.trim() || mutation.isPending}
            style={({ pressed }) => [
              styles.cta,
              (pressed || mutation.isPending || !name.trim()) && {
                opacity: 0.6,
              },
            ]}
          >
            <Text style={styles.ctaText}>
              {mutation.isPending ? 'Creando…' : 'Crear deuda y registrar'}
            </Text>
          </Pressable>
        </>
      )}
    </View>
  );
}

export function looksLikeFinancedOperation(
  description: string | null,
): boolean {
  if (!description) return false;
  const lower = description.toLowerCase();
  return (
    lower.includes('operacion financiada') ||
    lower.includes('operación financiada') ||
    lower.includes('operacion fraccionada') ||
    lower.includes('operación fraccionada') ||
    lower.includes('tarjeta financiada') ||
    lower.includes('compra a plazos')
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
  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    marginBottom: spacing.xs,
  },
  title: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  suggestedChip: {
    paddingVertical: 1,
    paddingHorizontal: spacing.xs,
    borderRadius: radius.sm,
    backgroundColor: colors.primarySoft,
  },
  suggestedChipText: {
    fontSize: 10,
    fontWeight: fontWeight.semibold,
    color: colors.primary,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
  },
  hint: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    marginBottom: spacing.sm,
    lineHeight: 18,
  },
  empty: {
    fontSize: fontSize.sm,
    color: colors.textSubtle,
    fontStyle: 'italic',
  },
  tabs: {
    flexDirection: 'row',
    gap: spacing.xs,
    marginBottom: spacing.sm,
  },
  tab: {
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  tabActive: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primary,
  },
  tabText: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    fontWeight: fontWeight.medium,
  },
  tabTextActive: {
    color: colors.primary,
    fontWeight: fontWeight.semibold,
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
    marginBottom: spacing.sm,
  },
  chip: {
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipSelected: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primary,
  },
  chipText: { fontSize: fontSize.sm, color: colors.text },
  chipTextSelected: { color: colors.primary, fontWeight: fontWeight.semibold },
  fieldLabel: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    color: colors.text,
    marginBottom: spacing.xs,
  },
  input: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
    fontSize: fontSize.md,
    color: colors.text,
    marginBottom: spacing.sm,
  },
  row: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  cta: {
    alignSelf: 'flex-start',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.primary,
    marginTop: spacing.xs,
  },
  ctaText: {
    color: colors.onPrimary,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
  },
});
