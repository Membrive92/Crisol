'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

import { useAuthStore } from '@finanzas/store';
import { authApi } from '@finanzas/services';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { isAuthenticated, isHydrated, accessToken, refreshToken, setTokens, setUser, logout } =
    useAuthStore();

  useEffect(() => {
    if (!isHydrated) return;

    if (!isAuthenticated && !refreshToken) {
      router.replace('/login');
      return;
    }

    if (!accessToken && refreshToken) {
      authApi
        .refresh(refreshToken)
        .then((tokens) => {
          setTokens(tokens.access_token, tokens.refresh_token);
          return authApi.getMe();
        })
        .then((user) => setUser(user))
        .catch(() => {
          logout();
          router.replace('/login');
        });
      return;
    }

    if (accessToken && !useAuthStore.getState().user) {
      authApi
        .getMe()
        .then((user) => setUser(user))
        .catch(() => {
          logout();
          router.replace('/login');
        });
    }
  }, [isHydrated, isAuthenticated, accessToken, refreshToken, setTokens, setUser, logout, router]);

  if (!isHydrated || !isAuthenticated) {
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
        <span style={{ fontSize: fontSize.lg, fontWeight: fontWeight.semibold, color: colors.primary }}>
          Finanzas
        </span>
        <Link href="/home" style={{ color: colors.text, textDecoration: 'none' }}>
          Inicio
        </Link>
        <Link href="/transactions" style={{ color: colors.text, textDecoration: 'none' }}>
          Transacciones
        </Link>
      </nav>
      {children}
    </div>
  );
}
