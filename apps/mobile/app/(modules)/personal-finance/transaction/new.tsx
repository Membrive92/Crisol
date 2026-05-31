import { useRouter } from 'expo-router';

import { useCreateTransaction } from '@crisol/services';
import { toast } from '@crisol/store';
import type { TransactionCreateRequest } from '@crisol/types';

import { TransactionForm } from '../../../../components/transaction-form';

export default function NewTransactionScreen() {
  const router = useRouter();
  const mutation = useCreateTransaction();

  function handleSubmit(payload: TransactionCreateRequest) {
    mutation.mutate(payload, {
      onSuccess: (created) => {
        // AUDIT-2026-05: el toast de budget vive ahora en la app (antes
        // en el hook; `@crisol/services` ya no importa `@crisol/store`).
        const alert = created.budget_alert;
        if (alert) {
          toast.show({
            kind: alert.status === 'over' ? 'error' : 'warning',
            message: alert.next_due_label,
            dedupKey: `budget:${alert.budget_id}`,
          });
        }
        router.back();
      },
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
