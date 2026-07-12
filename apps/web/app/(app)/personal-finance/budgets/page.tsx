'use client';

import { useState } from 'react';

import { formatApiError, useCategories, useUserCurrencies } from '@crisol/services';
import {
  useBudgetStatus,
  useBudgets,
  useCreateBudget,
  useDeleteBudget,
  useUpdateBudget,
} from '@crisol/services';
import { toast } from '@crisol/store';
import type { BudgetCreateRequest } from '@crisol/types';
import { colors, fontSize, fontWeight, layout, spacing } from '@crisol/ui';

import { BudgetForm } from '@/components/budgets/budget-form';
import { BudgetRow } from '@/components/budgets/budget-row';
import { BudgetStatusCard } from '@/components/budgets/budget-status-card';
import { Card } from '@/components/ui/card';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { ErrorState } from '@/components/ui/error-state';
import { Skeleton } from '@/components/ui/skeleton';

export default function BudgetsPage() {
  const { data: categories } = useCategories();
  const { data: currencies } = useUserCurrencies();
  const budgetsQuery = useBudgets();
  const statusQuery = useBudgetStatus();
  const createMutation = useCreateBudget();
  const updateMutation = useUpdateBudget();
  const deleteMutation = useDeleteBudget();

  const budgets = budgetsQuery.data ?? [];
  const statusItems = statusQuery.data?.items ?? [];
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  function handleCreate(data: BudgetCreateRequest) {
    createMutation.mutate(data, {
      onSuccess: () => toast.success('Presupuesto creado.'),
      onError: (err) =>
        toast.error(formatApiError(err, 'Error al crear el presupuesto.')),
    });
  }

  function handleDelete(id: string) {
    setPendingDeleteId(id);
  }

  function confirmDelete() {
    const id = pendingDeleteId;
    if (!id) return;
    setPendingDeleteId(null);
    deleteMutation.mutate(id, {
      onSuccess: () => toast.success('Presupuesto cerrado.'),
      onError: (err) =>
        toast.error(formatApiError(err, 'Error al cerrar el presupuesto.')),
    });
  }

  function handleSaveAmount(id: string, amount: string) {
    return new Promise<void>((resolve) => {
      updateMutation.mutate(
        { id, data: { amount } },
        {
          onSuccess: () => {
            toast.success('Importe actualizado.');
            resolve();
          },
          onError: (err) => {
            toast.error(formatApiError(err, 'Error al actualizar el importe.'));
            resolve();
          },
        },
      );
    });
  }

  return (
    <div style={{ maxWidth: layout.pageWide, margin: '0 auto', padding: spacing.lg }}>
      <header style={{ marginBottom: spacing.xl }}>
        <h1
          style={{
            margin: 0,
            fontSize: fontSize.xxl,
            fontWeight: fontWeight.bold,
            color: colors.text,
            letterSpacing: '-0.02em',
            lineHeight: 1.1,
          }}
        >
          Presupuestos
        </h1>
        <p
          style={{
            margin: `${spacing.xs}px 0 0 0`,
            color: colors.textMuted,
            fontSize: fontSize.sm,
          }}
        >
          Define un límite mensual por categoría (o global). El estado
          compara el gasto del mes en curso con tu límite.
        </p>
      </header>

      <section style={{ marginBottom: spacing.xl }}>
        <h2 style={sectionHeaderStyle}>Estado del mes</h2>
        {statusQuery.isLoading ? (
          <div
            aria-busy
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
              gap: spacing.md,
            }}
          >
            {Array.from({ length: 3 }, (_, i) => (
              <Skeleton key={i} height={96} />
            ))}
          </div>
        ) : statusQuery.isError ? (
          <ErrorState
            description="No se pudo cargar el estado de tus presupuestos."
            onRetry={() => void statusQuery.refetch()}
            retrying={statusQuery.isFetching}
          />
        ) : statusItems.length === 0 ? (
          <Card
            style={{
              padding: spacing.lg,
              textAlign: 'center',
              backgroundColor: colors.surfaceMuted,
              border: `1px dashed ${colors.border}`,
            }}
          >
            <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
              Aún no tienes presupuestos. Crea el primero abajo.
            </p>
          </Card>
        ) : (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
              gap: spacing.md,
            }}
          >
            {statusItems.map((item) => (
              <BudgetStatusCard
                key={item.budget.id}
                item={item}
                categories={categories ?? []}
              />
            ))}
          </div>
        )}
      </section>

      <section style={{ marginBottom: spacing.xl }}>
        <h2 style={sectionHeaderStyle}>Crear nuevo</h2>
        <Card style={{ padding: spacing.lg }}>
          <BudgetForm
            categories={categories ?? []}
            {...(currencies ? { currencies } : {})}
            submitting={createMutation.isPending}
            onSubmit={handleCreate}
          />
        </Card>
      </section>

      {budgetsQuery.isError ? (
        <section>
          <h2 style={sectionHeaderStyle}>Presupuestos activos</h2>
          <ErrorState
            description="No se pudo cargar la lista de presupuestos."
            onRetry={() => void budgetsQuery.refetch()}
            retrying={budgetsQuery.isFetching}
          />
        </section>
      ) : budgets.length > 0 ? (
        <section>
          <h2 style={sectionHeaderStyle}>Presupuestos activos</h2>
          <Card style={{ padding: 0 }}>
            <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
              {budgets.map((b, idx) => {
                const busy =
                  (deleteMutation.isPending && deleteMutation.variables === b.id) ||
                  (updateMutation.isPending && updateMutation.variables?.id === b.id);
                return (
                  <BudgetRow
                    key={b.id}
                    budget={b}
                    categories={categories ?? []}
                    onSave={handleSaveAmount}
                    onDelete={handleDelete}
                    busy={busy}
                    withTopBorder={idx > 0}
                  />
                );
              })}
            </ul>
          </Card>
        </section>
      ) : null}

      <ConfirmDialog
        open={pendingDeleteId !== null}
        title="¿Cerrar este presupuesto?"
        description="Quedará archivado a partir de hoy y dejará de contarse en el estado."
        confirmLabel="Cerrar presupuesto"
        cancelLabel="Atrás"
        tone="danger"
        loading={deleteMutation.isPending}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDeleteId(null)}
      />
    </div>
  );
}

const sectionHeaderStyle: React.CSSProperties = {
  fontSize: fontSize.lg,
  fontWeight: fontWeight.semibold,
  color: colors.text,
  marginTop: 0,
  marginBottom: spacing.md,
};
