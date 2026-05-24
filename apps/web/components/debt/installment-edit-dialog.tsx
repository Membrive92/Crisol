'use client';

import { useEffect, useState } from 'react';

import { useUpdateInstallment } from '@crisol/services';
import type { AmortizationRow } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

import { Button } from '@/components/ui/button';
import { TextInput } from '@/components/ui/field';

interface Props {
  installment: AmortizationRow | null;
  currency: string;
  onClose: () => void;
  onError: (err: unknown) => void;
}

/**
 * PHASE-24.1 — modal de edición puntual de una cuota.
 *
 * El backend NO recomputa las cuotas siguientes; es un override
 * puntual (útil cuando BBVA cobra algo distinto al cuadro francés
 * teórico por redondeos o comisiones).
 */
export function InstallmentEditDialog({ installment, currency, onClose, onError }: Props) {
  const mutation = useUpdateInstallment();
  const [payment, setPayment] = useState<string>('');
  const [dueDate, setDueDate] = useState<string>('');

  useEffect(() => {
    if (installment) {
      setPayment(installment.payment);
      setDueDate(installment.due_date);
    }
  }, [installment]);

  if (!installment || !installment.id) return null;

  function handleSubmit() {
    if (!installment?.id) return;
    const payload: { payment?: string; due_date?: string } = {};
    const trimmedPayment = payment.trim().replace(',', '.');
    if (trimmedPayment && trimmedPayment !== installment.payment) {
      payload.payment = trimmedPayment;
    }
    if (dueDate && dueDate !== installment.due_date) {
      payload.due_date = dueDate;
    }
    if (Object.keys(payload).length === 0) {
      onClose();
      return;
    }
    mutation.mutate(
      { installmentId: installment.id, payload },
      {
        onSuccess: () => onClose(),
        onError,
      },
    );
  }

  return (
    <div
      role="dialog"
      aria-modal
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0,0,0,0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100,
        padding: spacing.lg,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          backgroundColor: colors.surface,
          borderRadius: radius.lg,
          padding: spacing.lg,
          maxWidth: 420,
          width: '100%',
          boxShadow: '0 10px 40px rgba(0,0,0,0.3)',
        }}
      >
        <h2
          style={{
            margin: 0,
            marginBottom: spacing.xs,
            fontSize: fontSize.lg,
            fontWeight: fontWeight.semibold,
            color: colors.text,
          }}
        >
          Editar cuota #{installment.month}
        </h2>
        <p
          style={{
            margin: `0 0 ${spacing.md}px 0`,
            fontSize: fontSize.xs,
            color: colors.textMuted,
            lineHeight: 1.4,
          }}
        >
          Override puntual. Las cuotas siguientes NO se recalculan —
          mantienen los importes originales del cuadro francés.
          Moneda: {currency}.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
          <TextInput
            label="Importe"
            value={payment}
            onChange={(e) => setPayment(e.target.value)}
            inputMode="decimal"
          />
          <TextInput
            label="Fecha"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
            type="date"
          />
        </div>

        {mutation.isError ? (
          <p
            style={{
              marginTop: spacing.sm,
              color: colors.danger,
              fontSize: fontSize.sm,
            }}
          >
            {mutation.error instanceof Error
              ? mutation.error.message
              : 'Error al guardar'}
          </p>
        ) : null}

        <div
          style={{
            display: 'flex',
            justifyContent: 'flex-end',
            gap: spacing.sm,
            marginTop: spacing.md,
          }}
        >
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="button" onClick={handleSubmit} disabled={mutation.isPending}>
            {mutation.isPending ? 'Guardando…' : 'Guardar'}
          </Button>
        </div>
      </div>
    </div>
  );
}
