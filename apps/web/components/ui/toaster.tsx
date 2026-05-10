'use client';

import { useEffect, useState } from 'react';

import { useToastStore } from '@finanzas/store';
import type { Toast, ToastKind } from '@finanzas/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

import { XIcon } from './icons';
import { Spinner } from './spinner';

/**
 * Renderiza la queue de toasts globales en una stack fixed
 * top-right. Se monta una vez en el root del layout
 * (`apps/web/app/(app)/layout.tsx`); cualquier código del módulo
 * dispara toasts vía `toast.show(...)` o `useToastStore.getState().show(...)`.
 */
export function Toaster() {
  const toasts = useToastStore((s) => s.toasts);

  if (toasts.length === 0) return null;

  return (
    <div
      // El container es non-interactive (los toasts individuales sí
      // tienen botones). Coloca encima de cualquier modal/header que
      // pueda haber (z-index 50 = header en este repo).
      style={{
        position: 'fixed',
        top: spacing.lg,
        right: spacing.lg,
        zIndex: 1000,
        display: 'flex',
        flexDirection: 'column',
        gap: spacing.sm,
        // Ancho fijo razonable: suficiente para mensajes cortos +
        // acción sin ser un overlay molesto.
        width: 360,
        maxWidth: 'calc(100vw - 32px)',
        pointerEvents: 'none',
      }}
    >
      {toasts.map((t) => (
        <ToastCard key={t.id} toast={t} />
      ))}
    </div>
  );
}

function ToastCard({ toast }: { toast: Toast }) {
  const dismiss = useToastStore((s) => s.dismiss);

  // Auto-dismiss tras `dismissAfterMs`. `0` = manual.
  useEffect(() => {
    if (toast.dismissAfterMs <= 0) return;
    const timer = setTimeout(() => dismiss(toast.id), toast.dismissAfterMs);
    return () => clearTimeout(timer);
  }, [toast.id, toast.dismissAfterMs, dismiss]);

  const palette = paletteFor(toast.kind);
  const isLoading = toast.kind === 'loading';

  return (
    <div
      role="status"
      aria-live={toast.kind === 'error' ? 'assertive' : 'polite'}
      style={{
        pointerEvents: 'auto',
        backgroundColor: palette.bg,
        borderLeft: `3px solid ${palette.accent}`,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.md,
        padding: `${spacing.sm}px ${spacing.md}px`,
        display: 'flex',
        alignItems: 'center',
        gap: spacing.sm,
        boxShadow: '0 6px 16px rgba(0,0,0,0.12)',
      }}
    >
      {isLoading ? <Spinner size={18} color={palette.accent} /> : null}
      <span
        style={{
          flex: 1,
          fontSize: fontSize.sm,
          fontWeight: fontWeight.medium,
          color: colors.text,
          lineHeight: 1.4,
        }}
      >
        {toast.message}
        {isLoading ? <ElapsedTime /> : null}
      </span>
      {toast.action ? (
        <button
          type="button"
          onClick={() => {
            toast.action?.onPress();
            dismiss(toast.id);
          }}
          style={{
            backgroundColor: 'transparent',
            color: palette.accent,
            border: 'none',
            padding: `4px ${spacing.sm}px`,
            fontSize: fontSize.sm,
            fontWeight: fontWeight.semibold,
            cursor: 'pointer',
            borderRadius: radius.sm,
            whiteSpace: 'nowrap',
          }}
        >
          {toast.action.label}
        </button>
      ) : null}
      {/* Loading toasts no son dismissables manualmente — el caller
          los cierra con `toast.dismiss(id)` cuando termina la operación.
          Mostrar la X confunde (parece que cancelas la operación). */}
      {!isLoading ? (
        <button
          type="button"
          aria-label="Cerrar"
          onClick={() => dismiss(toast.id)}
          style={{
            backgroundColor: 'transparent',
            color: colors.textMuted,
            border: 'none',
            padding: 4,
            cursor: 'pointer',
            borderRadius: radius.sm,
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <XIcon size={14} />
        </button>
      ) : null}
    </div>
  );
}

/**
 * Cronómetro mm:ss que se actualiza cada segundo. Usado en toasts
 * `loading` para que el usuario vea que sigue trabajando.
 */
function ElapsedTime() {
  const [start] = useState(() => Date.now());
  const [now, setNow] = useState(start);
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const seconds = Math.floor((now - start) / 1000);
  const mm = Math.floor(seconds / 60).toString().padStart(2, '0');
  const ss = (seconds % 60).toString().padStart(2, '0');
  return (
    <span
      style={{
        marginLeft: spacing.xs,
        fontVariantNumeric: 'tabular-nums',
        color: colors.textMuted,
        fontWeight: fontWeight.regular,
      }}
    >
      ({mm}:{ss})
    </span>
  );
}

function paletteFor(kind: ToastKind): { bg: string; accent: string } {
  switch (kind) {
    case 'success':
      return { bg: colors.successSoft, accent: colors.success };
    case 'warning':
      return { bg: colors.warningSoft, accent: colors.warning };
    case 'error':
      return { bg: colors.dangerSoft, accent: colors.danger };
    case 'loading':
    case 'info':
    default:
      return { bg: colors.primarySoft, accent: colors.primary };
  }
}
