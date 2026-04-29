'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

import { useAuthStore } from '@finanzas/store';
import { authApi } from '@finanzas/services';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';

import { PasskeyPrompt } from '@/components/auth/passkey-prompt';
import { ThemeToggle } from '@/components/ui/theme-toggle';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { isAuthenticated, isHydrated, accessToken, setTokens, setUser, logout } =
    useAuthStore();
  const [bootstrapping, setBootstrapping] = useState(true);

  useEffect(() => {
    if (!isHydrated) return;
    let cancelled = false;

    // Si ya tenemos accessToken (tras login/registro), sólo hidratamos el
    // user con /me si aún no está cargado.
    if (accessToken) {
      if (!useAuthStore.getState().user) {
        authApi
          .getMe()
          .then((user) => {
            if (!cancelled) setUser(user);
          })
          .catch(() => {
            if (!cancelled) {
              logout();
              router.replace('/login');
            }
          });
      }
      setBootstrapping(false);
      return () => {
        cancelled = true;
      };
    }

    // Sin accessToken: intentamos refrescar usando la cookie httpOnly. Si
    // no hay cookie (o expiró), el backend devuelve 401 y vamos a login.
    authApi
      .refresh()
      .then((tokens) => {
        if (cancelled) return null;
        setTokens(tokens.access_token, tokens.refresh_token);
        return authApi.getMe();
      })
      .then((user) => {
        if (cancelled || !user) return;
        setUser(user);
      })
      .catch(() => {
        if (cancelled) return;
        logout();
        router.replace('/login');
      })
      .finally(() => {
        if (!cancelled) setBootstrapping(false);
      });

    return () => {
      cancelled = true;
    };
  }, [isHydrated, accessToken, setTokens, setUser, logout, router]);

  async function handleLogout() {
    try {
      await authApi.logout();
    } finally {
      logout();
      router.replace('/login');
    }
  }

  if (!isHydrated || bootstrapping || !isAuthenticated) {
    return null;
  }

  return (
    <div style={{ minHeight: '100vh', backgroundColor: colors.background }}>
      <nav
        style={{
          display: 'flex',
          gap: spacing.lg,
          alignItems: 'center',
          padding: `${spacing.md}px ${spacing.lg}px`,
          backgroundColor: colors.surface,
          borderBottom: `1px solid ${colors.border}`,
        }}
      >
        <span
          style={{
            fontSize: fontSize.lg,
            fontWeight: fontWeight.semibold,
            color: colors.primary,
          }}
        >
          Finanzas
        </span>
        <Link href="/dashboard" style={{ color: colors.text, textDecoration: 'none' }}>
          Dashboard
        </Link>
        <Link href="/transactions" style={{ color: colors.text, textDecoration: 'none' }}>
          Transacciones
        </Link>
        <Link href="/imports" style={{ color: colors.text, textDecoration: 'none' }}>
          Importar
        </Link>
        <Link href="/receipts" style={{ color: colors.text, textDecoration: 'none' }}>
          Tickets
        </Link>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: spacing.sm }}>
          <ThemeToggle />
        </div>
        <button
          type="button"
          onClick={handleLogout}
          style={{
            padding: `${spacing.xs}px ${spacing.sm}px`,
            backgroundColor: 'transparent',
            color: colors.danger,
            border: `1px solid ${colors.border}`,
            borderRadius: 6,
            cursor: 'pointer',
            fontSize: fontSize.sm,
            fontWeight: fontWeight.medium,
          }}
        >
          Cerrar sesión
        </button>
      </nav>
      <PasskeyPrompt />
      {children}
    </div>
  );
}
