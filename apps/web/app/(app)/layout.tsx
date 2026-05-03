'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';

import { useAuthStore } from '@finanzas/store';
import { authApi } from '@finanzas/services';
import { DEFAULT_MODULE_ID, findModuleByPath, getModule } from '@finanzas/types';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';

import { PasskeyPrompt } from '@/components/auth/passkey-prompt';
import { ModuleSidebar, SIDEBAR_WIDTH } from '@/components/modules/module-sidebar';
import { BellIcon, LogOutIcon, WalletIcon } from '@/components/ui/icons';
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
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: `0 ${spacing.lg}px`,
          backgroundColor: colors.surface,
          borderBottom: `1px solid ${colors.border}`,
          zIndex: 50,
        }}
      >
        <span
          style={{
            fontSize: fontSize.lg,
            fontWeight: fontWeight.bold,
            color: colors.text,
            letterSpacing: '-0.02em',
            width: SIDEBAR_WIDTH - spacing.lg,
          }}
        >
          Finanzas
        </span>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: spacing.xs,
            color: colors.textMuted,
          }}
        >
          <IconButton ariaLabel="Notificaciones">
            <BellIcon size={20} />
          </IconButton>
          <IconButton ariaLabel="Carteras">
            <WalletIcon size={20} />
          </IconButton>
          <ThemeToggle />
          <IconButton ariaLabel="Cerrar sesión" onClick={handleLogout}>
            <LogOutIcon size={20} />
          </IconButton>
        </div>
      </header>

      {activeModule && <ModuleSidebar active={activeModule} />}

      <main
        style={{
          paddingTop: 64,
          paddingLeft: SIDEBAR_WIDTH,
          minHeight: '100vh',
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
