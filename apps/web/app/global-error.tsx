'use client';

import { useEffect } from 'react';

/**
 * Boundary de último recurso (App Router). Sólo se activa cuando el
 * fallo ocurre en el propio `RootLayout`, así que debe renderizar su
 * propio `<html>`/`<body>` y no puede depender de providers ni de
 * `@crisol/ui` (el árbol está roto). Estilos inline literales a
 * propósito (AUDIT-2026-05).
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('[global] fatal render error:', error);
  }, [error]);

  return (
    <html lang="es">
      <body
        style={{
          margin: 0,
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          backgroundColor: '#fafafa',
          color: '#1f1f1f',
        }}
      >
        <div
          role="alert"
          style={{
            minHeight: '100vh',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 16,
            padding: 32,
            textAlign: 'center',
          }}
        >
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700 }}>
            La aplicación ha fallado
          </h1>
          <p style={{ margin: 0, fontSize: 14, color: '#666666', maxWidth: 440 }}>
            Ha ocurrido un error inesperado. Inténtalo de nuevo o recarga la
            página.
          </p>
          <button
            type="button"
            onClick={reset}
            style={{
              marginTop: 4,
              padding: '8px 24px',
              backgroundColor: '#c4671f',
              color: '#fff8f0',
              border: 'none',
              borderRadius: 8,
              fontSize: 14,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Reintentar
          </button>
        </div>
      </body>
    </html>
  );
}
