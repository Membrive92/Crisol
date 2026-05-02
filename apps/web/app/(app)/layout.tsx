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

  return (
    <div style={{ minHeight: '100vh', backgroundColor: colors.background }}>
      <header
        style={{
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: colors.surface,
          borderBottom: `1px solid ${colors.border}`,
        }}
      >
        <div
          style={{
            display: 'flex',
            gap: spacing.md,
            alignItems: 'center',
            padding: `${spacing.md}px ${spacing.lg}px`,
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
          {activeModule && <ModuleSwitcher active={activeModule} />}
          <div
            style={{
              marginLeft: 'auto',
              display: 'flex',
              gap: spacing.sm,
              alignItems: 'center',
            }}
          >
            <Link
              href="/settings"
              style={{
                color: colors.text,
                fontSize: fontSize.sm,
                fontWeight: fontWeight.medium,
                textDecoration: 'none',
                padding: `${spacing.xs}px ${spacing.sm}px`,
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
          </div>
        </div>
        {activeModule && activeModule.sections.length > 0 && (
          <nav
            style={{
              padding: `0 ${spacing.lg}px ${spacing.sm}px`,
            }}
          >
            <ModuleSections module={activeModule} />
          </nav>
        )}
      </header>
      <PasskeyPrompt />
      {children}
    </div>
  );
}
