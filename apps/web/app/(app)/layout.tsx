'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';

import { useAuthStore } from '@finanzas/store';
import { authApi } from '@finanzas/services';
import { DEFAULT_MODULE_ID, findModuleByPath, getModule } from '@finanzas/types';
import { colors, spacing } from '@finanzas/ui';

import { PasskeyPrompt } from '@/components/auth/passkey-prompt';
import { UserMenu } from '@/components/auth/user-menu';
import { CurrencyMenu } from '@/components/header/currency-menu';
import {
  AppSidebar,
  HEADER_HEIGHT,
  HEADER_HEIGHT_BARE,
  SIDEBAR_WIDTH,
} from '@/components/modules/app-sidebar';
import { ModuleSections } from '@/components/modules/module-sections';
import { BellIcon } from '@/components/ui/icons';
import { ThemeToggle } from '@/components/ui/theme-toggle';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, isAuthenticated, isHydrated, accessToken, setTokens, setUser, logout } =
    useAuthStore();
  const [bootstrapping, setBootstrapping] = useState(true);

  const activeModule = findModuleByPath(pathname ?? '') ?? getModule(DEFAULT_MODULE_ID);

  useEffect(() => {
    if (!isHydrated) return;
    let cancelled = false;

    if (accessToken) {
      if (!useAuthStore.getState().user) {
        authApi
          .getMe()
          .then((u) => {
            if (!cancelled) setUser(u);
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

    authApi
      .refresh()
      .then((tokens) => {
        if (cancelled) return null;
        setTokens(tokens.access_token, tokens.refresh_token);
        return authApi.getMe();
      })
      .then((u) => {
        if (cancelled || !u) return;
        setUser(u);
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
      {/* Sidebar fija con lista de MÓDULOS — full height para que el
          corner top-left de la pantalla pertenezca a la sidebar y no
          a un hueco del header. */}
      {activeModule && <AppSidebar active={activeModule} />}

      {/* Header fixed alineado con el contenido (empieza después de la
          sidebar). Así el corner sidebar-right ↔ header-bottom forma
          una L limpia en (240, 104). */}
      <header
        style={{
          position: 'fixed',
          top: 0,
          left: SIDEBAR_WIDTH,
          right: 0,
          // Chrome dark unified — el header comparte color con la sidebar
          // (`background`), no con las cards (`surface`). Esto evita que
          // la chrome compita visualmente con el contenido elevado.
          backgroundColor: colors.background,
          borderBottom: `1px solid ${colors.border}`,
          zIndex: 50,
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            gap: spacing.xs,
            padding: `0 ${spacing.lg}px`,
            height: 56,
            boxSizing: 'border-box',
          }}
        >
          <IconButton ariaLabel="Notificaciones">
            <BellIcon size={20} />
          </IconButton>
          <CurrencyMenu />
          <ThemeToggle />
          <UserMenu user={user} onLogout={handleLogout} />
        </div>

        {hasSections && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              padding: `0 ${spacing.lg}px`,
              height: 48,
              boxSizing: 'border-box',
              overflowX: 'auto',
            }}
          >
            <ModuleSections module={activeModule} />
          </div>
        )}
      </header>

      <main
        style={{
          paddingTop: hasSections ? HEADER_HEIGHT : HEADER_HEIGHT_BARE,
          paddingLeft: SIDEBAR_WIDTH,
          minHeight: '100vh',
          boxSizing: 'border-box',
        }}
      >
        <PasskeyPrompt />
        {children}
      </main>
    </div>
  );
}

function IconButton({
  children,
  ariaLabel,
  onClick,
}: {
  children: React.ReactNode;
  ariaLabel: string;
  onClick?: (() => void) | undefined;
}) {
  const [hovered, setHovered] = useState(false);
  return (
    <button
      type="button"
      aria-label={ariaLabel}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 36,
        height: 36,
        backgroundColor: hovered ? colors.surfaceMuted : 'transparent',
        color: hovered ? colors.text : colors.textMuted,
        border: 'none',
        borderRadius: 8,
        cursor: 'pointer',
        transition: 'background-color 120ms ease, color 120ms ease',
      }}
    >
      {children}
    </button>
  );
}
