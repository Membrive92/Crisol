import { useState } from 'react';
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { Stack } from 'expo-router';

import {
  formatApiError,
  useBudgets,
  useBudgetStatus,
  useCategories,
  useCreateBudget,
  useDeleteBudget,
  useUserCurrencies,
} from '@finanzas/services';
import { toast } from '@finanzas/store';
import type { BudgetCreateRequest } from '@finanzas/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

import { BudgetFormModal } from '../../../components/budgets/budget-form-modal';
import { BudgetStatusCard } from '../../../components/budgets/budget-status-card';

/**
 * Pantalla de presupuestos mobile (PHASE-12.3). Reusa los hooks
 * shared de PHASE-12.2. Layout vertical: estado del mes en cards
 * apiladas, sección de "tus presupuestos" con acciones cerrar, FAB
 * que abre el form modal.
 */
export default function BudgetsScreen() {
  const { data: categories } = useCategories();
  const { data: currencies } = useUserCurrencies();
  const budgetsQuery = useBudgets();
  const statusQuery = useBudgetStatus();
  const createMutation = useCreateBudget();
  const deleteMutation = useDeleteBudget();
  const [formOpen, setFormOpen] = useState(false);

  const budgets = budgetsQuery.data ?? [];
  const statusItems = statusQuery.data?.items ?? [];

  function handleCreate(data: BudgetCreateRequest) {
    createMutation.mutate(data, {
      onSuccess: () => {
        toast.success('Presupuesto creado.');
        setFormOpen(false);
      },
      onError: (err) =>
        toast.error(formatApiError(err, 'Error al crear el presupuesto.')),
    });
  }

  function handleDelete(id: string, label: string) {
    Alert.alert(
      'Cerrar presupuesto',
      `"${label}" quedará archivado a partir de hoy y dejará de contarse en el estado.`,
      [
        { text: 'Cancelar', style: 'cancel' },
        {
          text: 'Cerrar',
          style: 'destructive',
          onPress: () =>
            deleteMutation.mutate(id, {
              onSuccess: () => toast.success('Presupuesto cerrado.'),
              onError: (err) =>
                toast.error(formatApiError(err, 'Error al cerrar el presupuesto.')),
            }),
        },
      ],
    );
  }

  return (
    <View style={styles.container}>
      <Stack.Screen options={{ title: 'Presupuestos' }} />
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.sectionHeading}>Estado del mes</Text>
        {statusQuery.isLoading ? (
          <Text style={styles.placeholder}>Cargando…</Text>
        ) : statusItems.length === 0 ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyText}>
              Aún no tienes presupuestos. Toca el botón "+" abajo para crear el
              primero.
            </Text>
          </View>
        ) : (
          statusItems.map((item) => (
            <BudgetStatusCard
              key={item.budget.id}
              item={item}
              categories={categories ?? []}
            />
          ))
        )}

        {budgets.length > 0 ? (
          <>
            <Text style={[styles.sectionHeading, { marginTop: spacing.lg }]}>
              Presupuestos activos
            </Text>
            {budgets.map((b) => {
              const cat = (categories ?? []).find((c) => c.id === b.category_id);
              const label = cat?.name ?? 'Global';
              const busy =
                deleteMutation.isPending && deleteMutation.variables === b.id;
              return (
                <View key={b.id} style={styles.row}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.rowTitle}>{label}</Text>
                    <Text style={styles.rowMeta}>
                      {b.amount} {b.currency} / mes · desde {b.effective_from}
                    </Text>
                  </View>
                  <Pressable
                    onPress={() => handleDelete(b.id, label)}
                    disabled={busy}
                    style={({ pressed }) => [
                      styles.closeButton,
                      pressed && { opacity: 0.7 },
                      busy && { opacity: 0.5 },
                    ]}
                  >
                    <Text style={styles.closeButtonText}>
                      {busy ? 'Cerrando…' : 'Cerrar'}
                    </Text>
                  </Pressable>
                </View>
              );
            })}
          </>
        ) : null}
      </ScrollView>

      <Pressable
        onPress={() => setFormOpen(true)}
        style={({ pressed }) => [styles.fab, pressed && { opacity: 0.85 }]}
      >
        <Text style={styles.fabText}>+</Text>
      </Pressable>

      <BudgetFormModal
        visible={formOpen}
        categories={categories ?? []}
        {...(currencies ? { currencies } : {})}
        submitting={createMutation.isPending}
        onSubmit={handleCreate}
        onCancel={() => setFormOpen(false)}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.md, paddingBottom: spacing.xxl + 60 },
  sectionHeading: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
    marginBottom: spacing.sm,
  },
  placeholder: { padding: spacing.md, color: colors.textMuted },
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
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    gap: spacing.sm,
  },
  rowTitle: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  rowMeta: { fontSize: fontSize.xs, color: colors.textMuted, marginTop: 2 },
  closeButton: {
    paddingVertical: 6,
    paddingHorizontal: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
  },
  closeButtonText: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.semibold,
    color: colors.danger,
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
