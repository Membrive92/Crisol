'use client';

import type { ReactNode } from 'react';

import { colors, spacing } from '@finanzas/ui';

import { BrandPanel } from '@/components/auth/brand-panel';
import { ThemeToggle } from '@/components/ui/theme-toggle';

export interface AuthShellProps {
  children: ReactNode;
}

/**
 * Layout split de las páginas de auth:
 *  - Desktop (≥960px): panel de marca a la izquierda, formulario a la derecha.
 *  - Móvil/tablet: una sola columna; el panel de marca se reduce a una banda
 *    superior compacta (lo dejamos visible para mantener identidad sin
 *    saturar verticalmente).
 *
 * Toggle de tema fijo arriba-derecha sobre el panel del formulario para que
 * sea accesible antes de iniciar sesión.
 */
export function AuthShell({ children }: AuthShellProps) {
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'row',
        flexWrap: 'wrap',
        backgroundColor: colors.background,
      }}
      className="auth-shell"
    >
      <div className="auth-brand">
        <BrandPanel />
      </div>
      <div
        className="auth-form-side"
        style={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: spacing.xl,
          position: 'relative',
        }}
      >
        <div
          style={{
            position: 'absolute',
            top: spacing.md,
            right: spacing.md,
          }}
        >
          <ThemeToggle />
        </div>
        <div
          style={{
            width: '100%',
            maxWidth: 400,
          }}
        >
          {children}
        </div>
      </div>
    </div>
  );
}
