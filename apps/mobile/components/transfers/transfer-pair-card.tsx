import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { Account, TransferCandidate, TransferPair } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  formatDate,
  radius,
  spacing,
} from '@crisol/ui';

import { AccountSwatch } from '../accounts/account-swatch';

export interface TransferPairCardAction {
  label: string;
  onPress: () => void;
  busy?: boolean;
  /**
   * `ghost` para "Deshacer" (sólo borde) y `primary` para "Enlazar"
   * (relleno con color primario). Coherente con el card web equivalente.
   */
  variant?: 'primary' | 'ghost';
}

export interface TransferPairCardProps {
  /**
   * Soporta tanto pares ya emparejados (`TransferPair` viene de
   * `useTransfers`) como sugerencias del matcher (`TransferCandidate`
   * viene de `useTransferCandidates`). Tienen forma idéntica.
   */
  pair: TransferPair | TransferCandidate;
  accounts: Account[];
  /**
   * Acción primaria. En "pares activos" es "Deshacer"; en sugerencias
   * es "Enlazar". El caller controla label, handler y estado busy.
   */
  primaryAction: TransferPairCardAction;
}

/**
 * Card de un par de transferencia interna mobile (PHASE-19.3). Espejo
 * de `apps/web/components/transfers/transfer-pair-card.tsx`. Reusable
 * entre la sección "Pares activos" y "Sugerencias pendientes" — sólo
 * cambia la acción primaria (Deshacer / Enlazar).
 *
 * Layout vertical: importe + currency arriba, acción a la derecha,
 * dos legs (out / in) con swatch de cuenta + fecha + chip Δ Nd.
 */
export function TransferPairCard({ pair, accounts, primaryAction }: TransferPairCardProps) {
  const outAccount = accounts.find((a) => a.id === pair.out_account_id);
  const inAccount = accounts.find((a) => a.id === pair.in_account_id);
  const variant = primaryAction.variant ?? 'primary';

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <View style={styles.iconBubble} accessibilityElementsHidden>
            <Text style={styles.iconBubbleText}>⇄</Text>
          </View>
          <Text style={styles.amount}>
            {formatAmount(pair.amount, pair.currency)}
          </Text>
        </View>
        <Pressable
          onPress={primaryAction.onPress}
          disabled={primaryAction.busy}
          style={({ pressed }) => [
            variant === 'primary' ? styles.primaryButton : styles.ghostButton,
            pressed && styles.pressed,
            primaryAction.busy && styles.disabled,
          ]}
        >
          <Text
            style={
              variant === 'primary'
                ? styles.primaryButtonText
                : styles.ghostButtonText
            }
          >
            {primaryAction.busy ? '…' : primaryAction.label}
          </Text>
        </Pressable>
      </View>

      <View style={styles.divider} />

      <Leg
        arrow="↑"
        arrowColor={colors.expense}
        legend="Salida desde"
        accountName={outAccount?.name ?? 'Cuenta desconocida'}
        accountColor={outAccount?.color ?? null}
        accountIcon={outAccount?.icon ?? null}
        when={pair.out_occurred_at}
      />
      <Leg
        arrow="↓"
        arrowColor={colors.income}
        legend="Entrada en"
        accountName={inAccount?.name ?? 'Cuenta desconocida'}
        accountColor={inAccount?.color ?? null}
        accountIcon={inAccount?.icon ?? null}
        when={pair.in_occurred_at}
        deltaDays={pair.delta_days}
      />
    </View>
  );
}

interface LegProps {
  arrow: string;
  arrowColor: string;
  legend: string;
  accountName: string;
  accountColor: string | null;
  accountIcon: string | null;
  when: string;
  deltaDays?: number;
}

function Leg({
  arrow,
  arrowColor,
  legend,
  accountName,
  accountColor,
  accountIcon,
  when,
  deltaDays,
}: LegProps) {
  return (
    <View style={styles.leg}>
      <Text style={[styles.arrow, { color: arrowColor }]} accessibilityElementsHidden>
        {arrow}
      </Text>
      <Text style={styles.legLegend}>{legend}</Text>
      <AccountSwatch color={accountColor} icon={accountIcon} size={20} />
      <Text style={styles.legName} numberOfLines={1}>
        {accountName}
      </Text>
      <View style={styles.legDateBlock}>
        <Text style={styles.legDate}>{formatDate(when)}</Text>
        {deltaDays !== undefined && deltaDays > 0 ? (
          <View style={styles.deltaBadge}>
            <Text style={styles.deltaBadgeText}>Δ {deltaDays}d</Text>
          </View>
        ) : null}
      </View>
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
    marginBottom: spacing.sm,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    flex: 1,
    minWidth: 0,
  },
  iconBubble: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconBubbleText: {
    color: colors.primary,
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    lineHeight: fontSize.md + 2,
  },
  amount: {
    fontSize: fontSize.lg,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  primaryButton: {
    paddingVertical: 6,
    paddingHorizontal: spacing.sm + 2,
    borderRadius: radius.sm,
    backgroundColor: colors.primary,
  },
  primaryButtonText: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.semibold,
    color: colors.onPrimary,
  },
  ghostButton: {
    paddingVertical: 6,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: 'transparent',
  },
  ghostButtonText: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  pressed: { opacity: 0.7 },
  disabled: { opacity: 0.5 },
  divider: {
    height: 1,
    backgroundColor: colors.border,
    marginVertical: spacing.sm,
  },
  leg: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    paddingVertical: 2,
  },
  arrow: {
    width: 14,
    fontWeight: fontWeight.bold,
    fontSize: fontSize.sm,
    textAlign: 'center',
  },
  legLegend: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
  },
  legName: {
    flex: 1,
    minWidth: 0,
    fontSize: fontSize.sm,
    color: colors.text,
    fontWeight: fontWeight.medium,
  },
  legDateBlock: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  legDate: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
  },
  deltaBadge: {
    paddingHorizontal: spacing.xs,
    paddingVertical: 1,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceMuted,
  },
  deltaBadgeText: {
    fontSize: 11,
    fontWeight: fontWeight.semibold,
    color: colors.textMuted,
  },
});
