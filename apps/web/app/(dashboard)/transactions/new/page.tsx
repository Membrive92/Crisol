'use client';

import { useRouter } from 'next/navigation';

import { useCreateTransaction } from '@finanzas/services';
import type { TransactionCreateRequest } from '@finanzas/types';
import { colors, fontSize, spacing } from '@finanzas/ui';

import { TransactionForm } from '@/components/transactions/transaction-form';
import { Card } from '@/components/ui/card';

export default function NewTransactionPage() {
  const router = useRouter();
  const mutation = useCreateTransaction();

  function handleSubmit(payload: TransactionCreateRequest) {
    mutation.mutate(payload, {
      onSuccess: () => router.push('/transactions'),
    });
  }

  return (
    <div style={{ maxWidth: 560, margin: '0 auto', padding: spacing.lg }}>
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
