import { useMemo, useState } from 'react';
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import type { Account, Category, FixedExpense } from '@finanzas/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  formatDate,
  radius,
  spacing,
} from '@finanzas/ui';

export interface FixedExpenseCardAction {
  label: string;
  onPress: () => void;
  busy?: boolean;
  danger?: boolean;
}

export interface FixedExpenseCardProps {
  fixedExpense: FixedExpense;
  categories: Category[];
  /** PHASE-19.1 — cuentas disponibles para asignar al cobro. */
  accounts?: Account[];
  primaryAction?: FixedExpenseCardAction;
  secondaryAction?: FixedExpenseCardAction;
  /** PHASE-17.2 — toggle auto-post. Si se pasa el handler, aparece un check. */
  onToggleAutoPost?: (id: string, next: boolean) => void;
  autoPostBusy?: boolean;
  /** PHASE-19.1 — handler para cambiar la cuenta de cobro. `null` desactiva autopost. */
  onChangeAccount?: (id: string, accountId: string | null) => void;
  accountBusy?: boolean;
}

const CADENCE_LABEL: Record<number, string> = {
  7: 'Semanal',
  14: 'Quincenal',
  30: 'Mensual',
  90: 'Trimestral',
  180: 'Semestral',
  365: 'Anual',
};

function findCategory(categories: Category[], id: string | null): Category | undefined {
  if (!id) return undefined;
  return categories.find((c) => c.id === id);
}

function findAccount(accounts: Account[], id: string | null): Account | undefined {
  if (!id) return undefined;
  return accounts.find((a) => a.id === id);
}

/**
 * Card de gasto fijo mobile equivalente a la versión web. Misma
 * propuesta: callers controlan acciones vía primaryAction /
 * secondaryAction props (Confirmar+Descartar para pending,
 * Pausar+Cancelar para confirmed, etc.).
 *
 * PHASE-19.1: cuando el caller pasa `onChangeAccount` aparece un
 * selector inline de cuenta. Si la cuenta es null muestra un warning
 * indicando que el autopost no funcionará.
 */
export function FixedExpenseCard({
  fixedExpense: item,
  categories,
  accounts,
  primaryAction,
  secondaryAction,
  onToggleAutoPost,
  autoPostBusy,
  onChangeAccount,
  accountBusy,
}: FixedExpenseCardProps) {
  const category = findCategory(categories, item.category_id);
  const cadenceLabel = CADENCE_LABEL[item.cadence_days] ?? `${item.cadence_days}d`;
  const confidencePct = Math.round(item.confidence * 100);
  const accountList = useMemo(() => accounts ?? [], [accounts]);
  const showAccountSelector = onChangeAccount !== undefined && accountList.length > 0;
  const currentAccount = findAccount(accountList, item.account_id);
  const [pickerOpen, setPickerOpen] = useState(false);
  const autoPostDisabled = autoPostBusy || item.account_id === null;

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <View style={{ flex: 1, marginRight: spacing.sm }}>
          <Text style={styles.title} numberOfLines={1}>
            {item.raw_description}
          </Text>
          <Text style={styles.meta}>
            {cadenceLabel} · {category?.name ?? 'Sin categoría'} · confianza{' '}
            {confidencePct}%
          </Text>
        </View>
        <Text style={styles.amount}>{formatAmount(item.amount, item.currency)}</Text>
      </View>

      <View style={styles.divider} />

      {showAccountSelector ? (
        <View style={styles.accountRow}>
          <Text style={styles.accountLabel}>Cuenta:</Text>
          <Pressable
            onPress={() => setPickerOpen(true)}
            disabled={accountBusy}
            style={({ pressed }) => [
              styles.accountChip,
              pressed && { opacity: 0.7 },
              accountBusy && { opacity: 0.5 },
            ]}
          >
            <Text style={styles.accountChipText}>
              {currentAccount
                ? `${currentAccount.icon ? `${currentAccount.icon} ` : ''}${currentAccount.name} (${currentAccount.currency})`
                : '— Sin cuenta —'}
            </Text>
          </Pressable>
          {item.account_id === null ? (
            <Text style={styles.accountWarning}>
              Sin cuenta — el autopost no funcionará.
            </Text>
          ) : null}
        </View>
      ) : null}

      {onToggleAutoPost ? (
        <Pressable
          onPress={() => onToggleAutoPost(item.id, !item.auto_post)}
          disabled={autoPostDisabled}
          style={({ pressed }) => [
            styles.autoPostRow,
            pressed && { opacity: 0.7 },
            autoPostDisabled && { opacity: 0.5 },
          ]}
        >
          <View
            style={[
              styles.checkbox,
              item.auto_post && styles.checkboxActive,
            ]}
          >
            {item.auto_post ? <Text style={styles.checkmark}>✓</Text> : null}
          </View>
          <Text
            style={[
              styles.autoPostLabel,
              item.auto_post && { color: colors.primary, fontWeight: fontWeight.semibold },
            ]}
          >
            {item.account_id === null
              ? 'Asigna una cuenta para activar auto-añadir'
              : `Auto-añadir cada ${CADENCE_LABEL[item.cadence_days]?.toLowerCase() ?? 'ciclo'}`}
          </Text>
        </Pressable>
      ) : null}

      <View style={styles.footer}>
        <Text style={styles.footerText} numberOfLines={2}>
          Próximo cargo:{' '}
          <Text style={styles.footerStrong}>{formatDate(item.next_due)}</Text>
          {' · '}
          {item.occurrence_count}{' '}
          {item.occurrence_count === 1 ? 'cargo' : 'cargos'}
        </Text>
        <View style={styles.actions}>
          {secondaryAction ? (
            <Pressable
              onPress={secondaryAction.onPress}
              disabled={secondaryAction.busy}
              style={({ pressed }) => [
                styles.actionButton,
                pressed && styles.pressed,
                secondaryAction.busy && styles.disabled,
              ]}
            >
              <Text
                style={[
                  styles.actionText,
                  { color: secondaryAction.danger ? colors.danger : colors.text },
                ]}
              >
                {secondaryAction.busy ? '…' : secondaryAction.label}
              </Text>
            </Pressable>
          ) : null}
          {primaryAction ? (
            <Pressable
              onPress={primaryAction.onPress}
              disabled={primaryAction.busy}
              style={({ pressed }) => [
                styles.primaryButton,
                pressed && styles.pressed,
                primaryAction.busy && styles.disabled,
              ]}
            >
              <Text style={styles.primaryButtonText}>
                {primaryAction.busy ? '…' : primaryAction.label}
              </Text>
            </Pressable>
          ) : null}
        </View>
      </View>

      {showAccountSelector ? (
        <Modal
          visible={pickerOpen}
          transparent
          animationType="fade"
          onRequestClose={() => setPickerOpen(false)}
        >
          <Pressable
            style={styles.pickerBackdrop}
            onPress={() => setPickerOpen(false)}
          >
            <Pressable
              style={styles.pickerSheet}
              onPress={(e) => e.stopPropagation()}
            >
              <Text style={styles.pickerTitle}>Cuenta de cobro</Text>
              <ScrollView style={{ maxHeight: 360 }}>
                <Pressable
                  onPress={() => {
                    setPickerOpen(false);
                    onChangeAccount?.(item.id, null);
                  }}
                  style={({ pressed }) => [
                    styles.pickerItem,
                    pressed && { opacity: 0.7 },
                  ]}
                >
                  <Text style={styles.pickerItemText}>— Sin cuenta —</Text>
                </Pressable>
                {accountList.map((a) => {
                  const selected = a.id === item.account_id;
                  return (
                    <Pressable
                      key={a.id}
                      onPress={() => {
                        setPickerOpen(false);
                        onChangeAccount?.(item.id, a.id);
                      }}
                      style={({ pressed }) => [
                        styles.pickerItem,
                        selected && styles.pickerItemSelected,
                        pressed && { opacity: 0.7 },
                      ]}
                    >
                      <Text
                        style={[
                          styles.pickerItemText,
                          selected && styles.pickerItemTextSelected,
                        ]}
                      >
                        {a.icon ? `${a.icon} ` : ''}
                        {a.name} ({a.currency})
                      </Text>
                    </Pressable>
                  );
                })}
              </ScrollView>
            </Pressable>
          </Pressable>
        </Modal>
      ) : null}
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
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
  },
  title: { fontSize: fontSize.md, fontWeight: fontWeight.semibold, color: colors.text },
  meta: { fontSize: fontSize.xs, color: colors.textMuted, marginTop: 2 },
  amount: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  divider: {
    height: 1,
    backgroundColor: colors.border,
    marginVertical: spacing.xs,
  },
  accountRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: spacing.xs,
    paddingVertical: spacing.xs,
  },
  accountLabel: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    fontWeight: fontWeight.medium,
  },
  accountChip: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.background,
  },
  accountChipText: {
    fontSize: fontSize.xs,
    color: colors.text,
    fontWeight: fontWeight.medium,
  },
  accountWarning: {
    fontSize: fontSize.xs,
    color: colors.warning,
    flexBasis: '100%',
  },
  footer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  footerText: { fontSize: fontSize.xs, color: colors.textMuted, flex: 1 },
  footerStrong: { color: colors.text, fontWeight: fontWeight.medium },
  actions: { flexDirection: 'row', gap: spacing.xs },
  actionButton: {
    paddingVertical: 6,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  actionText: { fontSize: fontSize.xs, fontWeight: fontWeight.semibold },
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
  pressed: { opacity: 0.7 },
  disabled: { opacity: 0.5 },
  autoPostRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    paddingVertical: spacing.xs,
  },
  checkbox: {
    width: 16,
    height: 16,
    borderRadius: 3,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surface,
  },
  checkboxActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  checkmark: {
    color: colors.onPrimary,
    fontSize: 11,
    fontWeight: fontWeight.bold,
    lineHeight: 14,
  },
  autoPostLabel: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
  },
  pickerBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.lg,
  },
  pickerSheet: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    width: '100%',
    maxWidth: 420,
    borderWidth: 1,
    borderColor: colors.border,
  },
  pickerTitle: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
    marginBottom: spacing.sm,
  },
  pickerItem: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.sm,
  },
  pickerItemSelected: {
    backgroundColor: colors.primarySoft,
  },
  pickerItemText: {
    fontSize: fontSize.sm,
    color: colors.text,
  },
  pickerItemTextSelected: {
    color: colors.primary,
    fontWeight: fontWeight.semibold,
  },
});
