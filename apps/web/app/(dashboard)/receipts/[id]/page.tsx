'use client';

import { useParams, useRouter } from 'next/navigation';

import { useConfirmReceipt, useReceipt, useRejectReceipt } from '@finanzas/services';
import type { ReceiptConfirmRequest } from '@finanzas/types';
import { colors, fontSize, formatDate, spacing } from '@finanzas/ui';

import {
  ExtractionSummary,
  ReceiptConfirmForm,
} from '@/components/receipts/confirm-form';
import { ReceiptStatusBadge } from '@/components/receipts/status-badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

export default function ReceiptDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params?.id;

  const { data: receipt, isLoading, isError, error } = useReceipt(id);
  const confirmMutation = useConfirmReceipt(id ?? '');
  const rejectMutation = useRejectReceipt(id ?? '');

  function handleConfirm(payload: ReceiptConfirmRequest) {
    if (!receipt) return;
    confirmMutation.mutate(payload, {
      onSuccess: () => router.push('/receipts'),
    });
  }

  function handleReject() {
    if (!receipt) return;
    if (!confirm('¿Rechazar este ticket? La transacción no se creará.')) return;
    rejectMutation.mutate();
  }

  return (
    <div style={{ maxWidth: 720, margin: '0 auto', padding: spacing.lg }}>
      <header style={{ marginBottom: spacing.lg }}>
        <Button variant="ghost" onClick={() => router.push('/receipts')}>
          ← Volver
        </Button>
        <h1
          style={{
            fontSize: fontSize.xl,
            color: colors.text,
            marginTop: spacing.sm,
            marginBottom: 0,
          }}
        >
          Detalle de ticket
        </h1>
      </header>

      <Card style={{ padding: spacing.lg }}>
        {isLoading ? (
          <p>Cargando…</p>
        ) : isError ? (
          <p style={{ color: colors.danger }}>
            Error: {error instanceof Error ? error.message : 'desconocido'}
          </p>
        ) : receipt ? (
          <>
            <div style={{ display: 'flex', gap: spacing.sm, alignItems: 'center', marginBottom: spacing.md }}>
              <ReceiptStatusBadge status={receipt.status} />
              <span style={{ fontSize: fontSize.sm, color: colors.textMuted }}>
                {formatDate(receipt.created_at)}
              </span>
            </div>

            {receipt.status === 'pending' ? (
              <>
                <ReceiptConfirmForm
                  extraction={receipt.extraction}
                  submitting={confirmMutation.isPending || rejectMutation.isPending}
                  errorMessage={
                    confirmMutation.isError
                      ? confirmMutation.error instanceof Error
                        ? confirmMutation.error.message
                        : 'Error al confirmar'
                      : null
                  }
                  onSubmit={handleConfirm}
                  onReject={handleReject}
                />
                <ExtractionSummary extraction={receipt.extraction} />
              </>
            ) : (
              <>
                <p style={{ color: colors.textMuted, fontSize: fontSize.sm }}>
                  Este ticket ya fue {receipt.status === 'confirmed' ? 'confirmado' : 'rechazado'}.
                </p>
                <ExtractionSummary extraction={receipt.extraction} />
              </>
            )}
          </>
        ) : (
          <p style={{ color: colors.textMuted }}>Recibo no encontrado.</p>
        )}
      </Card>
    </div>
  );
}
