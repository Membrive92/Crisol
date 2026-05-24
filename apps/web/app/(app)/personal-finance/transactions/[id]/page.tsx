'use client';

import { use, useState } from 'react';
import { useRouter } from 'next/navigation';

import {
  formatApiError,
  useTransaction,
  useUpdateTransaction,
} from '@crisol/services';
import { toast } from '@crisol/store';
import type { TransactionUpdateRequest } from '@crisol/types';
import { colors, fontSize, fontWeight, spacing } from '@crisol/ui';

import {
  ConvertToDebtDialog,
  looksLikeFinancedOperation,
} from '@/components/transfers/convert-to-debt-dialog';
import { MarkAsTransferModal } from '@/components/transfers/mark-as-transfer-modal';
import { TransactionForm } from '@/components/transactions/transaction-form';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

export default function EditTransactionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { data, isLoading, isError, error } = useTransaction(id);
  const mutation = useUpdateTransaction(id);
  // Punto de entrada al modal: lo abrimos en el detalle (no en la lista)
  // para no saturar las filas con un botón por tx. El usuario que quiera
  // catalogar/recatalogar una transferencia entra a la edición y la
  // marca desde allí.
  const [markingTransfer, setMarkingTransfer] = useState(false);

  function handleSubmit(payload: TransactionUpdateRequest) {
    mutation.mutate(payload, {
      // `back()` en vez de `push('/transactions')` para conservar
      // el `?offset=N` con el que el usuario llegó al detalle — así
      // vuelve a la misma página de la lista en la que estaba.
      onSuccess: () => router.back(),
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
        <>
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

          <Card style={{ marginTop: spacing.lg, padding: spacing.lg }}>
            <h2
              style={{
                margin: 0,
                marginBottom: spacing.xs,
                fontSize: fontSize.md,
                fontWeight: fontWeight.semibold,
                color: colors.text,
              }}
            >
              ¿Es un movimiento entre tus cuentas?
            </h2>
            <p
              style={{
                margin: `0 0 ${spacing.md}px 0`,
                fontSize: fontSize.sm,
                color: colors.textMuted,
                lineHeight: 1.4,
              }}
            >
              {data.transfer_pair_id === null
                ? 'Si esta transacción es una transferencia entre cuentas tuyas, márcalo aquí y elige la cuenta contraparte. La app crea el otro lado automáticamente y deja el par fuera del cashflow.'
                : 'Esta transacción ya forma parte de una transferencia. Puedes reasignarla a otra cuenta si la enlazaste mal — el enlace actual se deshará primero.'}
            </p>
            <Button type="button" onClick={() => setMarkingTransfer(true)}>
              {data.transfer_pair_id === null
                ? 'Marcar como transferencia'
                : 'Reasignar transferencia'}
            </Button>
          </Card>

          {data.transfer_pair_id === null &&
          looksLikeFinancedOperation(data.description) ? (
            <ConvertToDebtDialog
              transaction={data}
              onConverted={(pair) => {
                toast.success(
                  `Deuda registrada (${pair.amount} ${pair.currency}). Revisa el cuadro de amortización en la cuenta.`,
                );
                router.push('/personal-finance/accounts');
              }}
              onError={(err) =>
                toast.error(formatApiError(err, 'No se pudo registrar la deuda'))
              }
            />
          ) : null}

          <MarkAsTransferModal
            transaction={markingTransfer ? data : null}
            onCancel={() => setMarkingTransfer(false)}
            onSuccess={(pair) => {
              setMarkingTransfer(false);
              toast.show({
                kind: 'success',
                message: `Transferencia ${
                  data.transfer_pair_id === null ? 'creada' : 'reasignada'
                } (${pair.amount} ${pair.currency}).`,
                action: {
                  label: 'Ver transferencias',
                  onPress: () => router.push('/personal-finance/transfers'),
                },
              });
              router.back();
            }}
            onError={(err) =>
              toast.error(formatApiError(err, 'No se pudo crear la transferencia'))
            }
          />
        </>
      ) : null}
    </div>
  );
}
