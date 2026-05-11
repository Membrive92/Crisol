'use client';

import { use } from 'react';
import { useRouter } from 'next/navigation';

import {
  useTransaction,
  useUpdateTransaction,
} from '@crisol/services';
import type { TransactionUpdateRequest } from '@crisol/types';
import { colors, fontSize, spacing } from '@crisol/ui';

import { TransactionForm } from '@/components/transactions/transaction-form';
import { Card } from '@/components/ui/card';

export default function EditTransactionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { data, isLoading, isError, error } = useTransaction(id);
  const mutation = useUpdateTransaction(id);

  function handleSubmit(payload: TransactionUpdateRequest) {
    mutation.mutate(payload, {
      onSuccess: () => router.push('/personal-finance/transactions'),
    });
  }

  return (
    <div style={{ maxWidth: 560, margin: '0 auto', padding: spacing.lg }}>
      <h1 style={{ fontSize: fontSize.xl, color: colors.text, marginBottom: spacing.lg }}>
        Editar transacción
      </h1>
      {isLoading ? (
        <p>Cargando…</p>
      ) : isError ? (
        <p style={{ color: colors.danger }}>
          Error: {error instanceof Error ? error.message : 'no se pudo cargar'}
        </p>
      ) : data ? (
        <Card>
          <TransactionForm
            initial={data}
            submitLabel="Guardar"
            submitting={mutation.isPending}
            onSubmit={(payload) => handleSubmit(payload as TransactionUpdateRequest)}
            onCancel={() => router.back()}
          />
          {mutation.isError ? (
            <p style={{ color: colors.danger, marginTop: spacing.sm }}>
              {mutation.error instanceof Error ? mutation.error.message : 'Error al guardar'}
            </p>
          ) : null}
        </Card>
      ) : null}
    </div>
  );
}
