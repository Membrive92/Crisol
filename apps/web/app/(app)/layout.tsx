'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';

import { useAuthStore } from '@finanzas/store';
import { authApi } from '@finanzas/services';
import { DEFAULT_MODULE_ID, findModuleByPath, getModule } from '@finanzas/types';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';

import { PasskeyPrompt } from '@/components/auth/passkey-prompt';
import { ModuleSections } from '@/components/modules/module-sections';
import { ModuleSwitcher } from '@/components/modules/module-switcher';
import { ThemeToggle } from '@/components/ui/theme-toggle';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, isHydrated, accessToken, setTokens, setUser, logout } =
    useAuthStore();
  const [bootstrapping, setBootstrapping] = useState(true);

  const activeModule = findModuleByPath(pathname ?? '') ?? getModule(DEFAULT_MODULE_ID);

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

  const hasSections = !!activeModule && activeModule.sections.length > 0;

  return (
    <div style={{ minHeight: '100vh', backgroundColor: colors.background }}>
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: spacing.md,
          padding: `${spacing.sm + 2}px ${spacing.lg}px`,
          backgroundColor: colors.surface,
          borderBottom: `1px solid ${colors.border}`,
        }}
      >
        <span
          style={{
            fontSize: fontSize.lg,
            fontWeight: fontWeight.bold,
            color: colors.text,
            letterSpacing: '-0.01em',
            flex: '0 0 auto',
          }}
        >
          Finanzas
        </span>
        {activeModule && <ModuleSwitcher active={activeModule} />}
        {hasSections && (
          <nav
            aria-label="Secciones del módulo"
            style={{
              flex: '1 1 auto',
              minWidth: 0,
              overflowX: 'auto',
              marginLeft: spacing.sm,
            }}
          >
            <ModuleSections module={activeModule} />
          </nav>
        )}
        <div
          style={{
            marginLeft: hasSections ? 0 : 'auto',
            display: 'flex',
            gap: spacing.xs,
            alignItems: 'center',
            flex: '0 0 auto',
          }}
        >
          <Link
            href="/settings"
            style={{
              color: colors.textMuted,
              fontSize: fontSize.sm,
              fontWeight: fontWeight.medium,
              textDecoration: 'none',
              padding: `${spacing.xs}px ${spacing.sm}px`,
              borderRadius: 6,
            }}
          >
            Ajustes
          </Link>
          <ThemeToggle />
          <button
            type="button"
            onClick={handleLogout}
            style={{
              padding: `${spacing.xs}px ${spacing.sm}px`,
              backgroundColor: 'transparent',
              color: colors.textMuted,
              border: `1px solid ${colors.border}`,
              borderRadius: 6,
              cursor: 'pointer',
              fontSize: fontSize.sm,
              fontWeight: fontWeight.medium,
            }}
          >
            Salir
          </button>
        </div>
      </header>
      <PasskeyPrompt />
      {children}
    </div>
  );
}
