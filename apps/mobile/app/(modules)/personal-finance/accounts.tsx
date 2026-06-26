import { useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Stack, useRouter } from 'expo-router';

import {
  formatApiError,
  useAccountBalances,
  useAccounts,
  useCreateAccount,
  useDeleteAccount,
  useUpdateAccount,
} from '@crisol/services';
import { toast } from '@crisol/store';
import type { Account, AccountCreateRequest, AccountUpdateRequest } from '@crisol/types';
import { AMORTIZABLE_ACCOUNT_TYPES, LIABILITY_ACCOUNT_TYPES } from '@crisol/types';
import { colors, fontSize, fontWeight, formatAmount, radius, spacing } from '@crisol/ui';

import {
  AccountFormModal,
  type AccountFormValues,
} from '../../../components/accounts/account-form-modal';
import { AccountSwatch } from '../../../components/accounts/account-swatch';
import { DebtPaymentWizard } from '../../../components/accounts/debt-payment-wizard';
import { ConfirmDialog } from '../../../components/ui/confirm-dialog';

const TYPE_LABEL: Record<string, string> = {
  bank: 'Banco',
  savings: 'Ahorro',
  brokerage: 'Bróker',
  crypto: 'Crypto',
  cash: 'Efectivo',
  credit_card: 'Tarjeta',
  loan: 'Préstamo',
  mortgage: 'Hipoteca',
};

/**
 * Convierte el porcentaje del UI (ej. "3.5") a decimal serializado para
 * el backend (ej. "0.035"). Devuelve `null` si vacío o no numérico.
 */
function aprPercentToDecimal(percent: string): string | null {
  const trimmed = percent.trim().replace(',', '.');
  if (!trimmed) return null;
  const numeric = Number(trimmed);
  if (!Number.isFinite(numeric)) return null;
  return (numeric / 100).toString();
}

/**
 * Convierte un `AccountFormValues` a payload de creación, incluyendo
 * los campos de amortización si el tipo es loan/mortgage.
 */
function toCreatePayload(values: AccountFormValues): AccountCreateRequest {
  const payload: AccountCreateRequest = {
    name: values.name,
    type: values.type,
    currency: values.currency,
    color: values.color,
    icon: values.icon,
  };
  if (values.opening_balance) payload.opening_balance = values.opening_balance;
  if (AMORTIZABLE_ACCOUNT_TYPES.includes(values.type)) {
    const apr = aprPercentToDecimal(values.apr_percent);
    if (apr !== null) payload.apr = apr;
    const tae = aprPercentToDecimal(values.tae_percent);
    if (tae !== null) payload.tae = tae;
    const term = values.term_months.trim();
    if (term) payload.term_months = Number(term);
    const start = values.start_date.trim();
    if (start) payload.start_date = start;
    const totalRaw = values.total_to_pay.trim().replace(',', '.');
    if (totalRaw) payload.total_to_pay = totalRaw;
    const interestOnlyRaw = values.interest_only_first_payment.trim().replace(',', '.');
    if (interestOnlyRaw) payload.interest_only_first_payment = interestOnlyRaw;
  }
  // PHASE-30.5: vinculación contrato↔categoría sólo aplica a liabilities.
  const isLiability = ['credit_card', 'loan', 'mortgage'].includes(values.type);
  if (isLiability && values.category_id) {
    payload.category_id = values.category_id;
  }
  return payload;
}

/**
 * Variante de update: el campo `opening_balance` del form representa
 * el SALDO ACTUAL que el usuario quiere ver (web y mobile alineados).
 * Restamos los movimientos para derivar el opening_balance que persiste
 * — así current_balance final = lo que el usuario tecleó.
 *
 * `movementsBalance` lo pasa el caller desde la query de balances.
 */
function toUpdatePayload(
  values: AccountFormValues,
  movementsBalance?: string,
): AccountUpdateRequest {
  const payload: AccountUpdateRequest = {
    name: values.name,
    type: values.type,
    currency: values.currency,
    color: values.color,
    icon: values.icon,
  };
  const isAmortizable = AMORTIZABLE_ACCOUNT_TYPES.includes(values.type);
  // PHASE-24.3: para liabilities amortizables el `opening_balance` no
  // se controla aquí (vive en las cuotas; ajustar con "Regenerar").
  if (values.opening_balance && !isAmortizable) {
    if (movementsBalance !== undefined) {
      const userValue = Number(values.opening_balance.replace(',', '.'));
      const mov = Number(movementsBalance);
      payload.opening_balance =
        Number.isFinite(userValue) && Number.isFinite(mov)
          ? (userValue - mov).toFixed(2)
          : values.opening_balance;
    } else {
      payload.opening_balance = values.opening_balance;
    }
  }
  if (isAmortizable) {
    payload.apr = aprPercentToDecimal(values.apr_percent);
    payload.tae = aprPercentToDecimal(values.tae_percent);
    const term = values.term_months.trim();
    payload.term_months = term ? Number(term) : null;
    const start = values.start_date.trim();
    payload.start_date = start ? start : null;
    const totalRaw = values.total_to_pay.trim().replace(',', '.');
    payload.total_to_pay = totalRaw ? totalRaw : null;
    const interestOnlyRaw = values.interest_only_first_payment.trim().replace(',', '.');
    payload.interest_only_first_payment = interestOnlyRaw ? interestOnlyRaw : null;
  } else {
    payload.apr = null;
    payload.tae = null;
    payload.term_months = null;
    payload.start_date = null;
    payload.total_to_pay = null;
    payload.interest_only_first_payment = null;
  }
  // PHASE-30.5: vinculación contrato↔categoría. Liabilities envían el
  // id seleccionado o `null` (desvincular). Assets fuerzan null para
  // evitar valores residuales tras un cambio de tipo.
  const isLiabilityForCategory = ['credit_card', 'loan', 'mortgage'].includes(values.type);
  payload.category_id = isLiabilityForCategory && values.category_id ? values.category_id : null;
  return payload;
}

/**
 * Pantalla de gestión de cuentas mobile (PHASE-19.1, ampliada en
 * PHASE-22). Espejo de `categories.tsx`: lista agrupada (Activas /
 * Archivadas), FAB para crear, modal compartido para crear/editar.
 *
 * PHASE-22 — para cuentas liability:
 * - Saldo en rojo + badge "DEUDA".
 * - Botón "Pagar cuota" si está activa, abre `DebtPaymentWizard`.
 * - Link "Ver cuadro →" si tiene `apr`, `term_months` y `start_date`.
 *
 * Las cuentas con histórico no se pueden borrar — el backend devuelve
 * 409 con un detalle español que se muestra tal cual al usuario; en ese
 * caso debe archivarla en su lugar.
 */
export default function AccountsScreen() {
  const [includeArchived, setIncludeArchived] = useState(false);
  const list = useAccounts({ includeArchived });
  // PHASE-19.4: cruzamos con balances para mostrar `current_balance`
  // discreto en cada fila. Cuentas archivadas también vienen aquí.
  const balancesQuery = useAccountBalances();
  const createMutation = useCreateAccount();
  const deleteMutation = useDeleteAccount();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Account | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Account | null>(null);
  const [payingDebt, setPayingDebt] = useState<Account | null>(null);

  const items = list.data ?? [];
  const active = items.filter((a) => !a.is_archived);
  const archived = items.filter((a) => a.is_archived);
  const balanceByAccount = useMemo(() => {
    const map = new Map<
      string,
      { current_balance: string; movements_balance: string; currency: string }
    >();
    for (const item of balancesQuery.data?.items ?? []) {
      map.set(item.account_id, {
        current_balance: item.current_balance,
        movements_balance: item.movements_balance,
        currency: item.currency,
      });
    }
    return map;
  }, [balancesQuery.data]);

  function openCreate() {
    setEditing(null);
    setFormOpen(true);
  }

  function openEdit(account: Account) {
    setEditing(account);
    setFormOpen(true);
  }

  function handleCreate(values: AccountFormValues) {
    createMutation.mutate(toCreatePayload(values), {
      onSuccess: () => {
        toast.success('Cuenta creada.');
        setFormOpen(false);
      },
      onError: (err) => toast.error(formatApiError(err, 'No se pudo crear la cuenta.')),
    });
  }

  function confirmDelete() {
    if (!pendingDelete) return;
    const target = pendingDelete;
    setPendingDelete(null);
    deleteMutation.mutate(target.id, {
      onSuccess: () => toast.success('Cuenta eliminada.'),
      onError: (err) =>
        toast.error(formatApiError(err, 'No se pudo eliminar — archívala si tiene transacciones.')),
    });
  }

  return (
    <View style={styles.container}>
      <Stack.Screen options={{ title: 'Cuentas' }} />
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.intro}>
          Cada transacción, importación y ticket se imputa a una cuenta. Las cuentas con histórico
          no se pueden borrar — archívalas para conservar las transacciones.
        </Text>

        <Pressable
          onPress={() => setIncludeArchived((v) => !v)}
          style={({ pressed }) => [styles.secondaryButton, pressed && { opacity: 0.7 }]}
          accessibilityRole="switch"
          accessibilityState={{ checked: includeArchived }}
        >
          <Text style={styles.secondaryText}>
            {includeArchived ? 'Ocultar archivadas' : 'Mostrar archivadas'}
          </Text>
        </Pressable>

        {list.isLoading ? (
          <Text style={styles.placeholder}>Cargando…</Text>
        ) : list.isError ? (
          <Text style={styles.error}>{formatApiError(list.error, 'Error cargando cuentas.')}</Text>
        ) : items.length === 0 ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyText}>
              Aún no tienes cuentas. Toca "+" para crear la primera.
            </Text>
          </View>
        ) : (
          <>
            <AccountGroup
              title="Activas"
              items={active}
              balances={balanceByAccount}
              onEdit={openEdit}
              onDelete={setPendingDelete}
              onPayDebt={setPayingDebt}
            />
            {includeArchived ? (
              <AccountGroup
                title="Archivadas"
                items={archived}
                balances={balanceByAccount}
                onEdit={openEdit}
                onDelete={setPendingDelete}
                onPayDebt={setPayingDebt}
              />
            ) : null}
          </>
        )}
      </ScrollView>

      <Pressable
        onPress={openCreate}
        style={({ pressed }) => [styles.fab, pressed && { opacity: 0.85 }]}
        accessibilityLabel="Nueva cuenta"
      >
        <Text style={styles.fabText}>+</Text>
      </Pressable>

      {editing ? (
        <EditAccountModal
          visible={formOpen}
          account={editing}
          movementsBalance={balanceByAccount.get(editing.id)?.movements_balance}
          currentBalance={balanceByAccount.get(editing.id)?.current_balance}
          onClose={() => setFormOpen(false)}
        />
      ) : (
        <AccountFormModal
          visible={formOpen}
          initial={null}
          submitting={createMutation.isPending}
          onSubmit={handleCreate}
          onCancel={() => setFormOpen(false)}
        />
      )}

      <ConfirmDialog
        open={pendingDelete !== null}
        title="¿Eliminar cuenta?"
        description={
          pendingDelete
            ? `"${pendingDelete.name}" sólo se podrá eliminar si no tiene transacciones. Si tiene histórico, archívala en su lugar.`
            : undefined
        }
        confirmLabel="Eliminar"
        cancelLabel="Atrás"
        tone="danger"
        loading={deleteMutation.isPending}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
      />

      {payingDebt ? (
        <DebtPaymentWizard
          liabilityAccount={payingDebt}
          visible={payingDebt !== null}
          onClose={() => setPayingDebt(null)}
        />
      ) : null}
    </View>
  );
}

interface EditAccountModalProps {
  visible: boolean;
  account: Account;
  /** PHASE-24.x: movements_balance del account, para que toUpdatePayload
   * pueda derivar opening_balance desde el current_balance que escribe
   * el usuario en el form. */
  movementsBalance?: string | undefined;
  /** Saldo actual computado — se pasa al modal para prefill. */
  currentBalance?: string | undefined;
  onClose: () => void;
}

/**
 * Aislamos el ciclo de vida del hook `useUpdateAccount(id)` (necesita
 * el id en construcción) en un sub-componente que se re-monta al
 * cambiar la cuenta editada — mismo patrón que `EditCategoryModal`.
 */
function EditAccountModal({
  visible,
  account,
  movementsBalance,
  currentBalance,
  onClose,
}: EditAccountModalProps) {
  const update = useUpdateAccount(account.id);

  function handleSubmit(values: AccountFormValues) {
    update.mutate(toUpdatePayload(values, movementsBalance), {
      onSuccess: () => {
        toast.success('Cuenta actualizada.');
        onClose();
      },
      onError: (err) => toast.error(formatApiError(err, 'No se pudo guardar.')),
    });
  }

  // Para el prefill: pasamos al modal una copia del account con el
  // opening_balance override = currentBalance, para que la UI muestre
  // lo que el usuario debe (no el opening 0 crudo del convert-to-debt).
  const accountForForm =
    currentBalance !== undefined && currentBalance !== '0.00'
      ? { ...account, opening_balance: currentBalance }
      : account;

  return (
    <AccountFormModal
      visible={visible}
      initial={accountForForm}
      submitting={update.isPending}
      onSubmit={handleSubmit}
      onCancel={onClose}
    />
  );
}

interface AccountGroupProps {
  title: string;
  items: Account[];
  balances: Map<string, { current_balance: string; currency: string }>;
  onEdit: (a: Account) => void;
  onDelete: (a: Account) => void;
  onPayDebt: (a: Account) => void;
}

function AccountGroup({ title, items, balances, onEdit, onDelete, onPayDebt }: AccountGroupProps) {
  if (items.length === 0) {
    return (
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>{title}</Text>
        <View style={styles.emptyCard}>
          <Text style={styles.emptyText}>Ninguna en esta sección.</Text>
        </View>
      </View>
    );
  }
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>
        {title} · {items.length}
      </Text>
      <View style={styles.list}>
        {items.map((account, idx) => (
          <AccountRow
            key={account.id}
            account={account}
            balance={balances.get(account.id)}
            isFirst={idx === 0}
            onEdit={onEdit}
            onDelete={onDelete}
            onPayDebt={onPayDebt}
          />
        ))}
      </View>
    </View>
  );
}

interface AccountRowProps {
  account: Account;
  balance: { current_balance: string; currency: string } | undefined;
  isFirst: boolean;
  onEdit: (a: Account) => void;
  onDelete: (a: Account) => void;
  onPayDebt: (a: Account) => void;
}

function AccountRow({ account, balance, isFirst, onEdit, onDelete, onPayDebt }: AccountRowProps) {
  const router = useRouter();
  // AUDIT LOW#13 — desde mobile también se puede marcar la cuenta principal
  // (antes sólo existía el badge; la acción vivía sólo en web).
  const makeDefault = useUpdateAccount(account.id);
  const isLiability = LIABILITY_ACCOUNT_TYPES.includes(account.type);
  const isAmortizable = AMORTIZABLE_ACCOUNT_TYPES.includes(account.type);
  const hasFullAmortization =
    isAmortizable && !!account.apr && !!account.term_months && !!account.start_date;
  const balanceColor = isLiability ? colors.danger : colors.text;
  const balancePrefix = isLiability ? '-' : '';
  // Sólo cuentas de activo, activas y que no sean ya la principal (HIGH#2:
  // un pasivo no puede ser principal).
  const canMakeDefault = !isLiability && !account.is_archived && !account.is_default;

  function handleMakeDefault() {
    makeDefault.mutate(
      { is_default: true },
      {
        onSuccess: () => toast.success(`"${account.name}" es ahora tu cuenta principal.`),
        onError: (err) => toast.error(formatApiError(err, 'No se pudo marcar como principal.')),
      },
    );
  }

  return (
    <View style={[styles.row, isFirst && { borderTopWidth: 0 }]}>
      <View style={styles.rowMain}>
        <AccountSwatch color={account.color} icon={account.icon} />
        <View style={styles.rowBody}>
          <View style={styles.rowNameLine}>
            <Text style={styles.rowName} numberOfLines={1}>
              {account.name}
              {account.is_archived ? <Text style={styles.rowMutedSuffix}> (archivada)</Text> : null}
            </Text>
            {isLiability ? (
              <View style={styles.debtBadge}>
                <Text style={styles.debtBadgeText}>DEUDA</Text>
              </View>
            ) : null}
            {account.is_default ? (
              <View style={styles.defaultBadge}>
                <Text style={styles.defaultBadgeText}>PRINCIPAL</Text>
              </View>
            ) : null}
          </View>
          <Text style={styles.rowMeta} numberOfLines={1}>
            {TYPE_LABEL[account.type] ?? account.type} · {account.currency}
            {balance ? (
              <Text style={[styles.rowBalance, { color: balanceColor }]}>
                {' · '}
                {balancePrefix}
                {formatAmount(balance.current_balance, balance.currency)}
              </Text>
            ) : null}
          </Text>
          {hasFullAmortization ? (
            <Pressable
              onPress={() =>
                router.push({
                  pathname: '/(modules)/personal-finance/accounts/[id]/amortization',
                  params: { id: account.id },
                })
              }
              style={styles.amortLink}
            >
              <Text style={styles.amortLinkText}>Ver cuadro →</Text>
            </Pressable>
          ) : null}
        </View>
      </View>
      <View style={styles.rowActions}>
        {canMakeDefault ? (
          <Pressable
            onPress={handleMakeDefault}
            style={styles.rowAction}
            disabled={makeDefault.isPending}
          >
            <Text style={styles.rowActionText}>Hacer principal</Text>
          </Pressable>
        ) : null}
        {isLiability && !account.is_archived ? (
          <Pressable onPress={() => onPayDebt(account)} style={styles.rowAction}>
            <Text style={styles.rowActionText}>Pagar cuota</Text>
          </Pressable>
        ) : null}
        <Pressable onPress={() => onEdit(account)} style={styles.rowAction}>
          <Text style={styles.rowActionText}>Editar</Text>
        </Pressable>
        <Pressable onPress={() => onDelete(account)} style={styles.rowAction}>
          <Text style={[styles.rowActionText, { color: colors.danger }]}>Borrar</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.md, paddingBottom: spacing.xxl + 60 },
  intro: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    marginBottom: spacing.md,
    lineHeight: 18,
  },
  secondaryButton: {
    alignSelf: 'flex-start',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.sm,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.md,
  },
  secondaryText: { color: colors.text, fontWeight: fontWeight.medium },
  placeholder: { color: colors.textMuted, paddingVertical: spacing.md },
  error: { color: colors.danger, paddingVertical: spacing.md },
  emptyCard: {
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.border,
    borderStyle: 'dashed',
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.lg,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    textAlign: 'center',
  },
  section: { marginTop: spacing.md },
  sectionTitle: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.semibold,
    color: colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginBottom: spacing.sm,
  },
  list: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: 'hidden',
  },
  row: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    gap: spacing.sm,
  },
  rowMain: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
  },
  rowBody: { flex: 1, minWidth: 0 },
  rowNameLine: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    flexWrap: 'wrap',
  },
  rowName: {
    flexShrink: 1,
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: fontWeight.medium,
  },
  rowMutedSuffix: {
    color: colors.textMuted,
    fontSize: fontSize.xs,
    fontWeight: fontWeight.medium,
  },
  rowMeta: { fontSize: fontSize.xs, color: colors.textMuted, marginTop: 2 },
  rowBalance: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.semibold,
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
  defaultBadge: {
    backgroundColor: colors.primarySoft,
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: radius.sm,
  },
  defaultBadgeText: {
    fontSize: 10,
    fontWeight: fontWeight.semibold,
    color: colors.primary,
    letterSpacing: 0.4,
  },
  amortLink: {
    marginTop: spacing.xs,
    alignSelf: 'flex-start',
  },
  amortLinkText: {
    fontSize: fontSize.xs,
    color: colors.primary,
    fontWeight: fontWeight.medium,
  },
  rowActions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
    justifyContent: 'flex-end',
  },
  rowAction: {
    paddingHorizontal: spacing.xs,
    paddingVertical: spacing.xs,
  },
  rowActionText: {
    color: colors.primary,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.medium,
  },
  fab: {
    position: 'absolute',
    right: spacing.lg,
    bottom: spacing.lg,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 6,
  },
  fabText: { color: colors.onPrimary, fontSize: 28, lineHeight: 32 },
});
