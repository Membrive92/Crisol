import { useMemo } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { useAccountBalances, useAccounts } from '@finanzas/services';
import type { AccountBalance } from '@finanzas/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
} from '@finanzas/ui';

import { AccountSwatch } from './account-swatch';

/**
 * Card de saldo agregado por cuenta mobile (PHASE-19.4). Espejo de
 * `apps/web/components/accounts/balances-card.tsx`. Muestra:
 *  - Patrimonio neto en `reference_currency` (suma cruda).
 *  - Subtotales activos / pasivos.
 *  - Lista compacta de cuentas activas con su `current_balance`.
 *  - Warning si `mixed_currencies === true` (totales sin convertir).
 *
 * Las cuentas archivadas vienen en `data.items` pero se filtran del
 * desglose cruzando con `useAccounts({ includeArchived: true })` —
 * el backend ya las excluye de los totales.
 */
export function BalancesCard() {
  const { data, isLoading, isError } = useAccountBalances();
  // Necesitamos `is_archived` para filtrar el desglose; el payload de
  // balances no lo trae, así que cruzamos con la lista de cuentas.
  const { data: accounts } = useAccounts({ includeArchived: true });

  const archivedIds = useMemo(() => {
    const set = new Set<string>();
    for (const account of accounts ?? []) {
      if (account.is_archived) set.add(account.id);
    }
    return set;
  }, [accounts]);

  if (isLoading) {
    return (
      <View style={styles.card}>
        <Text style={styles.loadingText}>Cargando saldos…</Text>
      </View>
    );
  }

  if (isError || !data) {
    return (
      <View style={styles.card}>
        <Text style={styles.errorText}>Error cargando saldos por cuenta.</Text>
      </View>
    );
  }

  const activeItems = data.items.filter((item) => !archivedIds.has(item.account_id));

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <View style={styles.iconBubble} accessibilityElementsHidden>
          <Text style={styles.iconBubbleText}>💼</Text>
        </View>
        <View style={{ flex: 1, minWidth: 0 }}>
          <Text style={styles.eyebrow}>Patrimonio neto</Text>
          <Text style={styles.netWorth}>
            {formatAmount(data.net_worth, data.reference_currency)}
          </Text>
        </View>
      </View>

      <View style={styles.subtotalsRow}>
        <SubtotalRow
          label="Activos"
          value={formatAmount(data.total_assets, data.reference_currency)}
          color={colors.income}
        />
        <SubtotalRow
          label="Pasivos"
          value={formatAmount(data.total_liabilities, data.reference_currency)}
          color={colors.textMuted}
        />
      </View>

      {data.mixed_currencies ? (
        <View style={styles.warningBox}>
          <Text style={styles.warningIcon} accessibilityElementsHidden>
            ⚠
          </Text>
          <Text style={styles.warningText}>
            Las cuentas activas tienen monedas distintas — el total no convierte
            entre divisas.
          </Text>
        </View>
      ) : null}

      <View style={styles.list}>
        {activeItems.length === 0 ? (
          <Text style={styles.emptyText}>No hay cuentas activas.</Text>
        ) : (
          activeItems.map((item) => <BalanceRow key={item.account_id} item={item} />)
        )}
      </View>
    </View>
  );
}

interface SubtotalRowProps {
  label: string;
  value: string;
  color: string;
}

function SubtotalRow({ label, value, color }: SubtotalRowProps) {
  return (
    <View style={styles.subtotal}>
      <Text style={styles.subtotalLabel}>{label}:</Text>
      <Text style={[styles.subtotalValue, { color }]}>{value}</Text>
    </View>
  );
}

function BalanceRow({ item }: { item: AccountBalance }) {
  const isLiability = item.nature === 'liability';
  return (
    <View style={styles.row}>
      <AccountSwatch color={item.color} icon={item.icon} size={24} />
      <Text style={styles.rowName} numberOfLines={1}>
        {item.name}
      </Text>
      <Text
        style={[
          styles.rowAmount,
          isLiability && { color: colors.expense },
        ]}
      >
        {formatAmount(item.current_balance, item.currency)}
      </Text>
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
    marginBottom: spacing.md,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  iconBubble: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconBubbleText: {
    fontSize: fontSize.md,
    lineHeight: fontSize.md + 4,
  },
  eyebrow: {
    fontSize: 11,
    fontWeight: fontWeight.semibold,
    color: colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  netWorth: {
    fontSize: fontSize.xl,
    fontWeight: fontWeight.bold,
    color: colors.text,
    lineHeight: fontSize.xl + 4,
    marginTop: 2,
  },
  subtotalsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md,
    marginBottom: spacing.sm,
  },
  subtotal: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: spacing.xs,
  },
  subtotalLabel: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    fontWeight: fontWeight.medium,
  },
  subtotalValue: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
  },
  warningBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.xs,
    backgroundColor: colors.warningSoft,
    padding: spacing.sm,
    borderRadius: radius.sm,
    marginBottom: spacing.sm,
  },
  warningIcon: {
    color: colors.warning,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.bold,
  },
  warningText: {
    flex: 1,
    color: colors.warning,
    fontSize: fontSize.xs,
    lineHeight: 16,
  },
  list: {
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: spacing.sm,
    gap: spacing.xs,
  },
  emptyText: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  rowName: {
    flex: 1,
    minWidth: 0,
    fontSize: fontSize.sm,
    color: colors.text,
  },
  rowAmount: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  loadingText: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
  },
  errorText: {
    fontSize: fontSize.sm,
    color: colors.danger,
  },
});
