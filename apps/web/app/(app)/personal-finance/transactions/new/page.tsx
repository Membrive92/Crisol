'use client';

import { useRouter } from 'next/navigation';

import { useCreateTransaction } from '@crisol/services';
import { toast } from '@crisol/store';
import type { TransactionCreateRequest } from '@crisol/types';
import { colors, fontSize, layout, spacing } from '@crisol/ui';

import { TransactionForm } from '@/components/transactions/transaction-form';
import { Card } from '@/components/ui/card';

export default function NewTransactionPage() {
  const router = useRouter();
  const mutation = useCreateTransaction();

  function handleSubmit(payload: TransactionCreateRequest) {
    mutation.mutate(payload, {
      onSuccess: (created) => {
        // AUDIT-2026-05: el toast de budget vive ahora en la app (antes
        // en el hook). dedupKey por budget evita spam al crear varias
        // txs seguidas en la misma categoría (PHASE-15.1).
        const alert = created.budget_alert;
        if (alert) {
          toast.show({
            kind: alert.status === 'over' ? 'error' : 'warning',
            message: alert.next_due_label,
            dedupKey: `budget:${alert.budget_id}`,
          });
        }
        router.push('/personal-finance/transactions');
      },
    });
  }

  return (
    <div style={{ maxWidth: layout.pageNarrow, margin: '0 auto', padding: spacing.lg }}>
      <h1 style={{ fontSize: fontSize.xl, color: colors.text, marginBottom: spacing.lg }}>
        Nueva transacción
      </h1>
      <Card>
        <TransactionForm
          submitLabel="Crear"
          submitting={mutation.isPending}
          onSubmit={(payload) => handleSubmit(payload as TransactionCreateRequest)}
          onCancel={() => router.back()}
        />
        {mutation.isError ? (
          <p style={{ color: colors.danger, marginTop: spacing.sm }}>
            {mutation.error instanceof Error ? mutation.error.message : 'Error al crear'}
          </p>
        ) : null}
      </Card>
    </div>
  );
}
