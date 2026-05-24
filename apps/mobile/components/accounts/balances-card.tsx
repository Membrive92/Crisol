import { useMemo } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { useAccountBalances, useAccounts } from '@crisol/services';
import { useCurrencyStore } from '@crisol/store';
import type { AccountBalance } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
} from '@crisol/ui';

import { AccountSwatch } from './account-swatch';

/**
 * Card de saldo agregado por cuenta mobile (PHASE-19.4, ampliada en
 * PHASE-22). Espejo de `apps/web/components/accounts/balances-card.tsx`.
 *
 * - Patrimonio neto en `reference_currency` (suma cruda). Si es negativo
 *   se pinta en `colors.danger`.
 * - Subtotales Activos / Pasivos. Pasivos se muestra con prefijo "-"
 *   y sólo aparece cuando `total_liabilities > 0`.
 * - Desglose agrupado por nature (Activos primero, Pasivos luego).
 *   Cada fila liability muestra su `current_balance` en color expense
 *   con badge "DEUDA" para reforzar la semántica.
 * - Warning si `mixed_currencies === true` (totales sin convertir).
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
  const includeDebt = useCurrencyStore((s) => s.includeDebtInNetWorth);

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
  const assetItems = activeItems.filter((item) => item.nature === 'asset');
  const liabilityItems = activeItems.filter((item) => item.nature === 'liability');

  const hasLiabilities = Number(data.total_liabilities) > 0;
  // Cuando `includeDebt` está OFF la cifra grande muestra sólo activos.
  // El desglose de pasivos se mantiene visible.
  const displayWorth = includeDebt ? data.net_worth : data.total_assets;
  const netWorthNegative = Number(displayWorth) < 0;
  const netWorthColor = netWorthNegative ? colors.danger : colors.text;

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <View style={styles.iconBubble} accessibilityElementsHidden>
          <Text style={styles.iconBubbleText}>💼</Text>
        </View>
        <View style={{ flex: 1, minWidth: 0 }}>
          <View style={styles.eyebrowRow}>
            <Text style={styles.eyebrow}>Patrimonio neto</Text>
            {!includeDebt && hasLiabilities ? (
              <View style={styles.eyebrowBadge}>
                <Text style={styles.eyebrowBadgeText}>Sin deuda</Text>
              </View>
            ) : null}
          </View>
          <Text style={[styles.netWorth, { color: netWorthColor }]}>
            {formatAmount(displayWorth, data.reference_currency)}
          </Text>
        </View>
      </View>

      <View style={styles.subtotalsRow}>
        <SubtotalRow
          label="Activos"
          value={formatAmount(data.total_assets, data.reference_currency)}
          color={colors.income}
        />
        {hasLiabilities ? (
          <SubtotalRow
            label="Pasivos"
            value={`-${formatAmount(data.total_liabilities, data.reference_currency)}`}
            color={colors.danger}
          />
        ) : null}
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
          <>
            {assetItems.length > 0 ? (
              <BalanceGroup title="Activos" items={assetItems} />
            ) : null}
            {liabilityItems.length > 0 ? (
              <BalanceGroup title="Pasivos" items={liabilityItems} />
            ) : null}
          </>
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

interface BalanceGroupProps {
  title: string;
  items: AccountBalance[];
}

function BalanceGroup({ title, items }: BalanceGroupProps) {
  return (
    <View style={styles.group}>
      <Text style={styles.groupTitle}>{title}</Text>
      <View style={styles.groupBody}>
        {items.map((item) => (
          <BalanceRow key={item.account_id} item={item} />
        ))}
      </View>
    </View>
  );
}

function BalanceRow({ item }: { item: AccountBalance }) {
  const isLiability = item.nature === 'liability';
  const amountColor = isLiability ? colors.danger : colors.text;
  const amountPrefix = isLiability ? '-' : '';
  return (
    <View style={styles.row}>
      <AccountSwatch color={item.color} icon={item.icon} size={24} />
      <View style={styles.rowNameWrap}>
        <Text style={styles.rowName} numberOfLines={1}>
          {item.name}
        </Text>
        {isLiability ? (
          <View style={styles.debtBadge}>
            <Text style={styles.debtBadgeText}>DEUDA</Text>
          </View>
        ) : null}
      </View>
      <Text style={[styles.rowAmount, { color: amountColor }]}>
        {amountPrefix}
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
  eyebrowRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    flexWrap: 'wrap',
  },
  eyebrow: {
    fontSize: 11,
    fontWeight: fontWeight.semibold,
    color: colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  eyebrowBadge: {
    backgroundColor: colors.surfaceMuted,
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: radius.sm,
  },
  eyebrowBadgeText: {
    fontSize: 10,
    color: colors.textMuted,
    letterSpacing: 0.4,
  },
  netWorth: {
    fontSize: fontSize.xl,
    fontWeight: fontWeight.bold,
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
    gap: spacing.sm,
  },
  group: {
    gap: spacing.xs,
  },
  groupTitle: {
    fontSize: 11,
    fontWeight: fontWeight.semibold,
    color: colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  groupBody: {
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
  rowNameWrap: {
    flex: 1,
    minWidth: 0,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  rowName: {
    flexShrink: 1,
    fontSize: fontSize.sm,
    color: colors.text,
  },
  debtBadge: {
    backgroundColor: colors.dangerSoft,
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: radius.sm,
  },
  debtBadgeText: {
    fontSize: 10,
    fontWeight: fontWeight.semibold,
    color: colors.danger,
    letterSpacing: 0.4,
  },
  rowAmount: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
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
