import { useRouter } from 'expo-router';

import { useCreateTransaction } from '@finanzas/services';
import type { TransactionCreateRequest } from '@finanzas/types';

import { TransactionForm } from '../../components/transaction-form';

export default function NewTransactionScreen() {
  const router = useRouter();
  const mutation = useCreateTransaction();

  function handleSubmit(payload: TransactionCreateRequest) {
    mutation.mutate(payload, {
      onSuccess: () => router.back(),
    });
  }

  return (
    <TransactionForm
      submitLabel="Crear"
      submitting={mutation.isPending}
      onSubmit={(payload) => handleSubmit(payload as TransactionCreateRequest)}
      onCancel={() => router.back()}
    />
  );
}
