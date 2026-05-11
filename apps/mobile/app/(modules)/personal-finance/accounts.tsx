import { useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Stack } from 'expo-router';

import {
  formatApiError,
  useAccountBalances,
  useAccounts,
  useCreateAccount,
  useDeleteAccount,
  useUpdateAccount,
} from '@crisol/services';
import { toast } from '@crisol/store';
import type {
  Account,
  AccountCreateRequest,
  AccountUpdateRequest,
} from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
} from '@crisol/ui';

import {
  AccountFormModal,
  type AccountFormValues,
} from '../../../components/accounts/account-form-modal';
import { AccountSwatch } from '../../../components/accounts/account-swatch';
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
 * Pantalla de gestión de cuentas mobile (PHASE-19.1). Espejo de
 * `categories.tsx`: lista agrupada (Activas / Archivadas), FAB para
 * crear, modal compartido para crear/editar.
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

  const items = list.data ?? [];
  const active = items.filter((a) => !a.is_archived);
  const archived = items.filter((a) => a.is_archived);
  const balanceByAccount = useMemo(() => {
    const map = new Map<string, { current_balance: string; currency: string }>();
    for (const item of balancesQuery.data?.items ?? []) {
      map.set(item.account_id, {
        current_balance: item.current_balance,
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
    const payload: AccountCreateRequest = {
      name: values.name,
      type: values.type,
      currency: values.currency,
      color: values.color,
      icon: values.icon,
      ...(values.opening_balance
        ? { opening_balance: values.opening_balance }
        : {}),
    };
    createMutation.mutate(payload, {
      onSuccess: () => {
        toast.success('Cuenta creada.');
        setFormOpen(false);
      },
      onError: (err) =>
        toast.error(formatApiError(err, 'No se pudo crear la cuenta.')),
    });
  }

  function confirmDelete() {
    if (!pendingDelete) return;
    const target = pendingDelete;
    setPendingDelete(null);
    deleteMutation.mutate(target.id, {
      onSuccess: () => toast.success('Cuenta eliminada.'),
      onError: (err) =>
        toast.error(
          formatApiError(
            err,
            'No se pudo eliminar — archívala si tiene transacciones.',
          ),
        ),
    });
  }

  return (
    <View style={styles.container}>
      <Stack.Screen options={{ title: 'Cuentas' }} />
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.intro}>
          Cada transacción, importación y ticket se imputa a una cuenta. Las
          cuentas con histórico no se pueden borrar — archívalas para conservar
          las transacciones.
        </Text>

        <Pressable
          onPress={() => setIncludeArchived((v) => !v)}
          style={({ pressed }) => [
            styles.secondaryButton,
            pressed && { opacity: 0.7 },
          ]}
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
          <Text style={styles.error}>
            {formatApiError(list.error, 'Error cargando cuentas.')}
          </Text>
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
            />
            {includeArchived ? (
              <AccountGroup
                title="Archivadas"
                items={archived}
                balances={balanceByAccount}
                onEdit={openEdit}
                onDelete={setPendingDelete}
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
    </View>
  );
}

interface EditAccountModalProps {
  visible: boolean;
  account: Account;
  onClose: () => void;
}

/**
 * Aislamos el ciclo de vida del hook `useUpdateAccount(id)` (necesita
 * el id en construcción) en un sub-componente que se re-monta al
 * cambiar la cuenta editada — mismo patrón que `EditCategoryModal`.
 */
function EditAccountModal({ visible, account, onClose }: EditAccountModalProps) {
  const update = useUpdateAccount(account.id);

  function handleSubmit(values: AccountFormValues) {
    const payload: AccountUpdateRequest = {
      name: values.name,
      type: values.type,
      currency: values.currency,
      color: values.color,
      icon: values.icon,
      ...(values.opening_balance
        ? { opening_balance: values.opening_balance }
        : {}),
    };
    update.mutate(payload, {
      onSuccess: () => {
        toast.success('Cuenta actualizada.');
        onClose();
      },
      onError: (err) =>
        toast.error(formatApiError(err, 'No se pudo guardar.')),
    });
  }

  return (
    <AccountFormModal
      visible={visible}
      initial={account}
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
}

function AccountGroup({
  title,
  items,
  balances,
  onEdit,
  onDelete,
}: AccountGroupProps) {
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
        {items.map((account, idx) => {
          const balance = balances.get(account.id);
          const isLiability = account.nature === 'liability';
          return (
            <View
              key={account.id}
              style={[styles.row, idx === 0 && { borderTopWidth: 0 }]}
            >
              <AccountSwatch color={account.color} icon={account.icon} />
              <View style={styles.rowBody}>
                <Text style={styles.rowName} numberOfLines={1}>
                  {account.name}
                  {account.is_archived ? (
                    <Text style={styles.rowMutedSuffix}> (archivada)</Text>
                  ) : null}
                </Text>
                <Text style={styles.rowMeta} numberOfLines={1}>
                  {TYPE_LABEL[account.type] ?? account.type} · {account.currency}
                  {balance ? (
                    <Text
                      style={[
                        styles.rowBalance,
                        isLiability && { color: colors.expense },
                      ]}
                    >
                      {' · '}
                      {formatAmount(balance.current_balance, balance.currency)}
                    </Text>
                  ) : null}
                </Text>
              </View>
              <Pressable onPress={() => onEdit(account)} style={styles.rowAction}>
                <Text style={styles.rowActionText}>Editar</Text>
              </Pressable>
              <Pressable
                onPress={() => onDelete(account)}
                style={styles.rowAction}
              >
                <Text style={[styles.rowActionText, { color: colors.danger }]}>
                  Borrar
                </Text>
              </Pressable>
            </View>
          );
        })}
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
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  rowBody: { flex: 1, minWidth: 0 },
  rowName: {
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
    color: colors.text,
    fontWeight: fontWeight.semibold,
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
