'use client';

import { useEffect } from 'react';

import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

/**
 * Error boundary de las rutas autenticadas (App Router). Captura
 * cualquier excepción de render lanzada por un segmento bajo `(app)/`
 * que no haya sido manejada por la propia página, evitando la pantalla
 * en blanco. `reset()` re-monta el segmento (AUDIT-2026-05).
 *
 * No usa el componente `ErrorState` compartido para no depender de que
 * el árbol de providers siga sano tras el fallo — se mantiene
 * autocontenido con tokens.
 */
export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Telemetría mínima en consola. En producción el `digest` permite
    // correlacionar con los logs del servidor sin exponer el stack.
    console.error('[app] unhandled render error:', error);
  }, [error]);

  return (
    <div
      role="alert"
      style={{
        minHeight: '60vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: spacing.md,
        padding: spacing.xl,
        textAlign: 'center',
      }}
    >
      <h1
        style={{
          margin: 0,
          fontSize: fontSize.xl,
          fontWeight: fontWeight.bold,
          color: colors.text,
        }}
      >
        Algo ha ido mal
      </h1>
      <p
        style={{
          margin: 0,
          fontSize: fontSize.sm,
          color: colors.textMuted,
          maxWidth: 440,
          lineHeight: 1.5,
        }}
      >
        No hemos podido mostrar esta sección. Puedes reintentar; si el
        problema persiste, recarga la página.
      </p>
      <button
        type="button"
        onClick={reset}
        style={{
          marginTop: spacing.xs,
          padding: `${spacing.sm}px ${spacing.lg}px`,
          backgroundColor: colors.primary,
          color: colors.onPrimary,
          border: 'none',
          borderRadius: radius.md,
          fontSize: fontSize.sm,
          fontWeight: fontWeight.semibold,
          cursor: 'pointer',
        }}
      >
        Reintentar
      </button>
    </div>
  );
}
