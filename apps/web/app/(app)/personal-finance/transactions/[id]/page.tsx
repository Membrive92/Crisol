'use client';

import { use, useState } from 'react';
import { useRouter } from 'next/navigation';

import { formatApiError, useTransaction, useUpdateTransaction } from '@crisol/services';
import { toast } from '@crisol/store';
import type { TransactionUpdateRequest } from '@crisol/types';
import { colors, fontSize, fontWeight, layout, spacing } from '@crisol/ui';

import { AmortizationPanel } from '@/components/transfers/amortization-panel';
import {
  ConvertToDebtDialog,
  looksLikeFinancedOperation,
} from '@/components/transfers/convert-to-debt-dialog';
import { MarkAsTransferModal } from '@/components/transfers/mark-as-transfer-modal';
import { ExceptionalToggle } from '@/components/transactions/exceptional-toggle';
import { TransactionForm } from '@/components/transactions/transaction-form';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

export default function EditTransactionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { data, isLoading, isError, error } = useTransaction(id);
  const mutation = useUpdateTransaction(id);
  // Mutación dedicada para el toggle estructural/puntual — separada de la del
  // form para que su `isPending` no interfiera con el botón "Guardar".
  const exceptionalMutation = useUpdateTransaction(id);
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
    <div style={{ maxWidth: layout.pageWide, margin: '0 auto', padding: spacing.lg }}>
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
        // Layout en 2 columnas como el resto de vistas (pageWide): el
        // formulario a la izquierda y las tarjetas de acción/contexto a la
        // derecha. `flexWrap` las apila en pantallas estrechas. Cada columna
        // mantiene un ancho legible en vez de estirar los inputs a lo ancho.
        <div
          style={{ display: 'flex', flexWrap: 'wrap', gap: spacing.lg, alignItems: 'flex-start' }}
        >
          <div style={{ flex: '3 1 460px', maxWidth: layout.pageNarrow, minWidth: 0 }}>
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
          </div>

          <div
            style={{
              flex: '2 1 320px',
              minWidth: 0,
              display: 'flex',
              flexDirection: 'column',
              gap: spacing.lg,
            }}
          >
            <Card style={{ padding: spacing.lg }}>
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
                  ? 'Si esta transacción es un movimiento entre cuentas tuyas, márcalo aquí y elige la cuenta contraparte. Creamos el otro lado automáticamente y el par deja de contar como gasto o ingreso del mes.'
                  : 'Esta transacción ya forma parte de una transferencia. Puedes reasignarla a otra cuenta si la enlazaste mal — el enlace actual se deshará primero.'}
              </p>
              <Button type="button" onClick={() => setMarkingTransfer(true)}>
                {data.transfer_pair_id === null
                  ? 'Marcar como transferencia'
                  : 'Reasignar transferencia'}
              </Button>
            </Card>

            {data.flow === 'OUT' ? (
              <Card style={{ padding: spacing.lg }}>
                <h2
                  style={{
                    margin: 0,
                    marginBottom: spacing.xs,
                    fontSize: fontSize.md,
                    fontWeight: fontWeight.semibold,
                    color: colors.text,
                  }}
                >
                  Clasificación del gasto
                </h2>
                <p
                  style={{
                    margin: `0 0 ${spacing.md}px 0`,
                    fontSize: fontSize.sm,
                    color: colors.textMuted,
                    lineHeight: 1.4,
                  }}
                >
                  Los gastos <strong>variables</strong> (impuestos, dentista, reformas) se excluyen
                  de tu gasto fijo recurrente y del cálculo de colchón. Por defecto lo decide una
                  heurística; aquí puedes forzarlo.
                </p>
                <ExceptionalToggle
                  value={data.is_exceptional ?? null}
                  pending={exceptionalMutation.isPending}
                  onChange={(next) =>
                    exceptionalMutation.mutate(
                      { is_exceptional: next },
                      {
                        onSuccess: () => toast.success('Clasificación actualizada.'),
                        onError: (err) =>
                          toast.error(
                            formatApiError(err, 'No se pudo actualizar la clasificación'),
                          ),
                      },
                    )
                  }
                />
              </Card>
            ) : null}

            {/* PHASE-45 — sólo para salidas de dinero sin emparejar: una tx ya
                emparejada tiene su contrapartida moviendo el dinero, y añadir
                una amortización bajaría la deuda dos veces (el backend lo
                rechaza con 409). */}
            {data.transfer_pair_id === null &&
            (data.flow === 'OUT' || data.flow === 'TRANSFER_OUT') ? (
              <AmortizationPanel transaction={data} />
            ) : null}

            {data.transfer_pair_id === null ? (
              <ConvertToDebtDialog
                transaction={data}
                suggested={looksLikeFinancedOperation(data.description)}
                onConverted={(pair) => {
                  toast.success(
                    `Deuda registrada (${pair.amount} ${pair.currency}). Revisa el cuadro de amortización en la cuenta.`,
                  );
                  // La lista de cuentas en web vive en /settings/accounts
                  // (bajo /personal-finance/accounts sólo existe la ruta
                  // [id]/amortization). Antes empujaba a /personal-finance/
                  // accounts → 404.
                  router.push('/settings/accounts');
                }}
                onError={(err) => toast.error(formatApiError(err, 'No se pudo registrar la deuda'))}
              />
            ) : null}
          </div>

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
                  label: 'Ver transacciones',
                  onPress: () => router.push('/personal-finance/transactions'),
                },
              });
              router.back();
            }}
            onError={(err) => toast.error(formatApiError(err, 'No se pudo crear la transferencia'))}
          />
        </div>
      ) : null}
    </div>
  );
}
