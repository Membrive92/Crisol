import type { ReactNode } from 'react';

import { colors, radius, spacing } from '@finanzas/ui';

import { ThemeToggle } from '@/components/ui/theme-toggle';

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: spacing.xl,
        backgroundColor: colors.background,
      }}
    >
      <div
        style={{
          position: 'fixed',
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
          backgroundColor: colors.surface,
          borderRadius: radius.md,
          padding: spacing.xl,
          border: `1px solid ${colors.border}`,
          // Sombra sutil que se ve en light pero apenas en dark — usa rgba
          // negro de baja opacidad, así que dark "absorbe" el efecto.
          boxShadow: '0 2px 12px rgba(0, 0, 0, 0.08)',
        }}
      >
        {children}
      </div>
    </div>
  );
}
