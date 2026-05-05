'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

import { Button } from '@/components/ui/button';

export interface TrashedBannerProps {
  /**
   * ID de la última transacción borrada. Cambiar este valor a un
   * nuevo string activa el banner; pasar `null` lo oculta. El banner
   * auto-desaparece tras `dismissAfterMs`.
   */
  lastDeletedId: string | null;
  onUndo: () => void;
  isRestoring: boolean;
  /** Por defecto 6s — suficiente para leer "deshacer" sin colgar. */
  dismissAfterMs?: number;
}

/**
 * Notificación inline tras un soft-delete: "Movido a papelera" +
 * acciones [Deshacer] y [Ver papelera]. Inline en lugar de toast
 * global porque el codebase no tiene aún un sistema de toasts; cuando
 * llegue uno (`Sonner`/`react-hot-toast`/propio) se reemplaza este
 * banner por una toast call.
 */
export function TrashedBanner({
  lastDeletedId,
  onUndo,
  isRestoring,
  dismissAfterMs = 6000,
}: TrashedBannerProps) {
  const [visibleId, setVisibleId] = useState<string | null>(null);

  // Sincroniza el visibleId con la prop. Cambiar `lastDeletedId` (un
  // nuevo borrado) reinicia el contador. Pasar `null` la oculta.
  useEffect(() => {
    setVisibleId(lastDeletedId);
  }, [lastDeletedId]);

  // Auto-dismiss tras N ms sin interacción.
  useEffect(() => {
    if (!visibleId) return;
    const timer = setTimeout(() => setVisibleId(null), dismissAfterMs);
    return () => clearTimeout(timer);
  }, [visibleId, dismissAfterMs]);

  if (!visibleId) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: spacing.md,
        padding: `${spacing.sm}px ${spacing.md}px`,
        backgroundColor: colors.surfaceMuted,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.md,
      }}
    >
      <span
        style={{
          fontSize: fontSize.sm,
          fontWeight: fontWeight.medium,
          color: colors.text,
        }}
      >
        Transacción movida a papelera.
      </span>
      <span style={{ display: 'inline-flex', gap: spacing.xs, alignItems: 'center' }}>
        <Button
          variant="ghost"
          onClick={() => {
            onUndo();
            setVisibleId(null);
          }}
          disabled={isRestoring}
          style={{ padding: `4px ${spacing.sm}px` }}
        >
          {isRestoring ? 'Restaurando…' : 'Deshacer'}
        </Button>
        <Link href="/personal-finance/trash">
          <Button variant="ghost" style={{ padding: `4px ${spacing.sm}px` }}>
            Ver papelera
          </Button>
        </Link>
      </span>
    </div>
  );
}
