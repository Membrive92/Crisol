'use client';

import { useReceiptImage } from '@finanzas/services';
import { colors, fontSize, radius, spacing } from '@finanzas/ui';

export interface ReceiptImageProps {
  receiptId: string;
}

export function ReceiptImage({ receiptId }: ReceiptImageProps) {
  const { url, isLoading, error } = useReceiptImage(receiptId);

  if (isLoading) {
    return (
      <div
        style={{
          padding: spacing.md,
          fontSize: fontSize.sm,
          color: colors.textMuted,
          textAlign: 'center',
          backgroundColor: colors.surfaceMuted,
          borderRadius: radius.sm,
        }}
      >
        Cargando imagen…
      </div>
    );
  }

  if (error || !url) {
    return (
      <div
        style={{
          padding: spacing.md,
          fontSize: fontSize.sm,
          color: colors.textMuted,
          textAlign: 'center',
          backgroundColor: colors.surfaceMuted,
          borderRadius: radius.sm,
        }}
      >
        No se pudo cargar la imagen del ticket.
      </div>
    );
  }

  return (
    <img
      src={url}
      alt="Imagen del ticket"
      style={{
        maxWidth: '100%',
        maxHeight: 480,
        display: 'block',
        margin: '0 auto',
        borderRadius: radius.sm,
        border: `1px solid ${colors.border}`,
      }}
    />
  );
}
