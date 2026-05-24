'use client';

import { usePayInstallment, useUnpayInstallment } from '@crisol/services';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

interface Props {
  installmentId: string;
  paid: boolean;
  onError: (err: unknown) => void;
}

/**
 * PHASE-24.1 — botón pay/unpay de una cuota. Sin tx vinculada en MVP
 * (el usuario puede vincular la tx desde el listado de transacciones
 * usando "Convertir en transferencia").
 */
export function InstallmentPayButtons({ installmentId, paid, onError }: Props) {
  const payMutation = usePayInstallment();
  const unpayMutation = useUnpayInstallment();
  const busy = payMutation.isPending || unpayMutation.isPending;

  function handleToggle() {
    if (paid) {
      unpayMutation.mutate(installmentId, { onError });
    } else {
      payMutation.mutate({ installmentId }, { onError });
    }
  }

  return (
    <button
      type="button"
      onClick={handleToggle}
      disabled={busy}
      style={{
        padding: `2px ${spacing.sm}px`,
        fontSize: fontSize.xs,
        fontWeight: fontWeight.semibold,
        color: paid ? colors.success : colors.onPrimary,
        backgroundColor: paid ? 'transparent' : colors.success,
        border: `1px solid ${colors.success}`,
        borderRadius: radius.sm,
        cursor: busy ? 'wait' : 'pointer',
        opacity: busy ? 0.6 : 1,
      }}
      title={paid ? 'Desmarcar como pagada' : 'Marcar como pagada'}
    >
      {paid ? '✓ Pagada' : 'Marcar pagada'}
    </button>
  );
}
