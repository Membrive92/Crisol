import { useMemo } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

import { useCategories } from '@crisol/services';
import type { Account, AccountBalance, Category } from '@crisol/types';
import { AMORTIZABLE_ACCOUNT_TYPES } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
} from '@crisol/ui';

import { AccountSwatch } from '../accounts/account-swatch';

const TYPE_LABEL: Record<string, string> = {
  credit_card: 'Tarjeta',
  loan: 'Préstamo',
  mortgage: 'Hipoteca',
};

export interface DebtListProps {
  /** Cuentas con saldo (vienen de `useAccountBalances`). */
  balances: AccountBalance[];
  /** Cuentas completas con apr/term/start_date (de `useAccounts`). */
  accounts: Account[];
  isLoading: boolean;
  /** Callback para abrir el wizard de pago de cuota. */
  onPayDebt: (account: Account) => void;
}

/**
 * Lista de pasivos con sus KPIs y acciones. Botones por fila:
 * "Pagar cuota" (todos) y "Ver cuadro" (sólo loan/mortgage con
 * amortización completa).
 */
export function DebtList({ balances, accounts, isLoading, onPayDebt }: DebtListProps) {
  const router = useRouter();

  const liabilities = useMemo(() => {
    return balances.filter((b) => b.nature === 'liability');
  }, [balances]);

  const accountById = useMemo(() => {
    const map = new Map<string, Account>();
    for (const a of accounts) map.set(a.id, a);
    return map;
  }, [accounts]);

  const categoriesQuery = useCategories();
  const categoriesById = useMemo(() => {
    const map = new Map<string, Category>();
    for (const c of categoriesQuery.data ?? []) map.set(c.id, c);
    return map;
  }, [categoriesQuery.data]);

  if (isLoading && liabilities.length === 0) {
    return (
      <View style={styles.card}>
        <View style={styles.skeletonRow} />
        <View style={styles.skeletonRow} />
      </View>
    );
  }

  if (liabilities.length === 0) {
    return (
      <View style={styles.card}>
        <Text style={styles.emptyTitle}>Aún no tienes deuda registrada</Text>
        <Text style={styles.emptyText}>
          Añade una tarjeta de crédito, un préstamo o una hipoteca desde
          Cuentas para empezar a monitorizar tu deuda.
        </Text>
        <Pressable
          style={({ pressed }) => [
            styles.primaryButton,
            pressed && { opacity: 0.85 },
          ]}
          onPress={() => router.push('/personal-finance/accounts')}
        >
          <Text style={styles.primaryButtonText}>Añadir deuda</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.card}>
      <Text style={styles.title}>Mis pasivos</Text>
      {liabilities.map((b) => {
        const full = accountById.get(b.account_id);
        const isAmortizable =
          full?.type === 'loan' || full?.type === 'mortgage';
        const canShowSchedule =
          full !== undefined &&
          AMORTIZABLE_ACCOUNT_TYPES.includes(full.type) &&
          full.apr !== null &&
          full.term_months !== null &&
          full.start_date !== null;
        return (
          <View key={b.account_id} style={styles.row}>
            <View style={styles.rowHeader}>
              <AccountSwatch color={b.color ?? null} icon={b.icon ?? null} />
              <View style={styles.rowHeaderMeta}>
                <Text style={styles.rowName} numberOfLines={1}>
                  {b.name}
                </Text>
                <View style={styles.rowTypeRow}>
                  <Text style={styles.rowType}>{TYPE_LABEL[b.type] ?? b.type}</Text>
                  {full?.category_id ? (() => {
                    const cat = categoriesById.get(full.category_id);
                    if (!cat) return null;
                    return (
                      <View style={styles.categoryChip}>
                        {cat.icon ? (
                          <Text style={styles.categoryChipIcon}>{cat.icon}</Text>
                        ) : null}
                        <Text style={styles.categoryChipText} numberOfLines={1}>
                          {cat.name}
                        </Text>
                      </View>
                    );
                  })() : null}
                </View>
              </View>
              <Text style={styles.rowBalance}>
                {formatAmount(b.current_balance, b.currency)}
              </Text>
            </View>
            {full?.apr !== null && full?.apr !== undefined ? (
              <View style={styles.metaRow}>
                <Text style={styles.metaLabel}>APR</Text>
                <Text style={styles.metaValue}>
                  {(Number(full.apr) * 100).toFixed(2)}%
                </Text>
                {isAmortizable && full.term_months ? (
                  <>
                    <Text style={styles.metaSep}>·</Text>
                    <Text style={styles.metaLabel}>Plazo</Text>
                    <Text style={styles.metaValue}>{full.term_months}m</Text>
                  </>
                ) : null}
              </View>
            ) : null}
            <View style={styles.actions}>
              {full !== undefined ? (
                <Pressable
                  style={({ pressed }) => [
                    styles.action,
                    styles.actionPrimary,
                    pressed && { opacity: 0.85 },
                  ]}
                  onPress={() => onPayDebt(full)}
                >
                  <Text style={styles.actionPrimaryText}>Pagar cuota</Text>
                </Pressable>
              ) : null}
              {canShowSchedule && full ? (
                <Pressable
                  style={({ pressed }) => [
                    styles.action,
                    styles.actionSecondary,
                    pressed && { opacity: 0.85 },
                  ]}
                  onPress={() =>
                    router.push(`/personal-finance/accounts/${full.id}/amortization`)
                  }
                >
                  <Text style={styles.actionSecondaryText}>Ver cuadro</Text>
                </Pressable>
              ) : null}
            </View>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  title: {
    fontSize: fontSize.lg,
    fontWeight: fontWeight.semibold,
    color: colors.text,
    marginBottom: spacing.md,
  },
  row: {
    paddingVertical: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  rowHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  rowHeaderMeta: {
    flex: 1,
    minWidth: 0,
  },
  rowName: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  rowType: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
  },
  rowTypeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    marginTop: 2,
    flexWrap: 'wrap',
  },
  categoryChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.primary,
  },
  categoryChipIcon: {
    fontSize: 11,
  },
  categoryChipText: {
    fontSize: 11,
    fontWeight: fontWeight.semibold,
    color: colors.primary,
    maxWidth: 120,
  },
  rowBalance: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.bold,
    color: colors.danger,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    marginTop: spacing.sm,
  },
  metaLabel: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  metaValue: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  metaSep: {
    fontSize: fontSize.sm,
    color: colors.textSubtle,
    marginHorizontal: spacing.xs,
  },
  actions: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  action: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
  },
  actionPrimary: {
    backgroundColor: colors.primary,
  },
  actionPrimaryText: {
    color: colors.onPrimary,
    fontWeight: fontWeight.semibold,
    fontSize: fontSize.sm,
  },
  actionSecondary: {
    backgroundColor: colors.surfaceMuted,
    borderWidth: 1,
    borderColor: colors.border,
  },
  actionSecondaryText: {
    color: colors.text,
    fontWeight: fontWeight.medium,
    fontSize: fontSize.sm,
  },
  emptyTitle: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
    marginBottom: spacing.xs,
  },
  emptyText: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    lineHeight: 20,
    marginBottom: spacing.md,
  },
  primaryButton: {
    backgroundColor: colors.primary,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    alignSelf: 'flex-start',
  },
  primaryButtonText: {
    color: colors.onPrimary,
    fontWeight: fontWeight.semibold,
    fontSize: fontSize.sm,
  },
  skeletonRow: {
    height: 56,
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.md,
    marginBottom: spacing.sm,
  },
});
