'use client';

import { formatApiError, useCategories, useUserCurrencies } from '@finanzas/services';
import {
  useBudgetStatus,
  useBudgets,
  useCreateBudget,
  useDeleteBudget,
} from '@finanzas/services';
import { toast } from '@finanzas/store';
import type { BudgetCreateRequest } from '@finanzas/types';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';

import { BudgetForm } from '@/components/budgets/budget-form';
import { BudgetStatusCard } from '@/components/budgets/budget-status-card';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

export default function BudgetsPage() {
  const { data: categories } = useCategories();
  const { data: currencies } = useUserCurrencies();
  const budgetsQuery = useBudgets();
  const statusQuery = useBudgetStatus();
  const createMutation = useCreateBudget();
  const deleteMutation = useDeleteBudget();

  const budgets = budgetsQuery.data ?? [];
  const statusItems = statusQuery.data?.items ?? [];

  function handleCreate(data: BudgetCreateRequest) {
    createMutation.mutate(data, {
      onSuccess: () => toast.success('Presupuesto creado.'),
      onError: (err) =>
        toast.error(formatApiError(err, 'Error al crear el presupuesto.')),
    });
  }

  function handleDelete(id: string) {
    if (
      !confirm(
        '¿Cerrar este presupuesto? Quedará archivado a partir de hoy y dejará de contarse en el estado.',
      )
    ) {
      return;
    }
    deleteMutation.mutate(id, {
      onSuccess: () => toast.success('Presupuesto cerrado.'),
      onError: (err) =>
        toast.error(formatApiError(err, 'Error al cerrar el presupuesto.')),
    });
  }

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: spacing.lg }}>
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
          <p style={{ color: colors.textMuted }}>Cargando…</p>
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

      {budgets.length > 0 ? (
        <section>
          <h2 style={sectionHeaderStyle}>Presupuestos activos</h2>
          <Card style={{ padding: 0 }}>
            <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
              {budgets.map((b, idx) => {
                const cat = (categories ?? []).find((c) => c.id === b.category_id);
                return (
                  <li
                    key={b.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: spacing.md,
                      borderTop: idx === 0 ? 'none' : `1px solid ${colors.border}`,
                    }}
                  >
                    <div>
                      <span
                        style={{
                          fontSize: fontSize.sm,
                          fontWeight: fontWeight.semibold,
                          color: colors.text,
                          display: 'block',
                        }}
                      >
                        {cat?.name ?? 'Global'}
                      </span>
                      <span style={{ fontSize: fontSize.xs, color: colors.textMuted }}>
                        {b.amount} {b.currency} / mes · vigente desde {b.effective_from}
                      </span>
                    </div>
                    <Button
                      variant="ghost"
                      onClick={() => handleDelete(b.id)}
                      disabled={
                        deleteMutation.isPending && deleteMutation.variables === b.id
                      }
                      style={{ color: colors.danger, borderColor: colors.border }}
                    >
                      {deleteMutation.isPending && deleteMutation.variables === b.id
                        ? 'Cerrando…'
                        : 'Cerrar'}
                    </Button>
                  </li>
                );
              })}
            </ul>
          </Card>
        </section>
      ) : null}
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
