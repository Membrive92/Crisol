'use client';

import type { ReactNode } from 'react';

import { colors } from '@finanzas/ui';

import { Toaster } from '@/components/ui/toaster';

/**
 * Layout standalone para la pantalla de onboarding bloqueante. Sin
 * sidebar, sin header — el flujo de "declarar primera cuenta" es lineal
 * y no debe permitir navegar a otras secciones hasta completarlo.
 */
export default function OnboardingLayout({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: colors.background,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {children}
      <Toaster />
    </div>
  );
}
