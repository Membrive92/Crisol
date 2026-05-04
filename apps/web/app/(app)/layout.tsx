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
  MOBILE_BREAKPOINT_PX,
  SIDEBAR_WIDTH,
} from '@/components/modules/app-sidebar';
import { ModuleSections } from '@/components/modules/module-sections';
import { BellIcon, MenuIcon } from '@/components/ui/icons';
import { ThemeToggle } from '@/components/ui/theme-toggle';

// Estilos globales del drawer mobile. Se inyectan vía `<style>` porque
// el layout usa `style={{}}` inline (sin CSS modules ni Tailwind), y
// las inline styles ganan a las reglas CSS sin `!important`. Las
// reglas con `!important` aquí baten al inline `style` del layout
// para colapsar offsets de sidebar y mostrar/ocultar elementos
// `data-mobile-only` según el breakpoint.
const MOBILE_NAV_GLOBAL_STYLES = `
  @media (max-width: ${MOBILE_BREAKPOINT_PX - 1}px) {
    [data-app-main] { padding-left: 0 !important; }
    [data-app-header] { left: 0 !important; }
    [data-app-sidebar] {
      transform: translateX(-100%);
      transition: transform 200ms ease;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
    }
    [data-app-sidebar][data-mobile-open="true"] {
      transform: translateX(0);
    }
    [data-mobile-only] { display: inline-flex !important; }
  }
  @media (min-width: ${MOBILE_BREAKPOINT_PX}px) {
    [data-mobile-only] { display: none !important; }
    [data-mobile-backdrop] { display: none !important; }
  }
`;

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, isAuthenticated, isHydrated, accessToken, setTokens, setUser, logout } =
    useAuthStore();
  const [bootstrapping, setBootstrapping] = useState(true);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const activeModule = findModuleByPath(pathname ?? '') ?? getModule(DEFAULT_MODULE_ID);

  // Cierra el drawer al cambiar de ruta (clic en cualquier item de la
  // sidebar). Sin esto el drawer quedaría visible tras navegar.
  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

  // ESC cierra el drawer cuando está abierto.
  useEffect(() => {
    if (!mobileNavOpen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setMobileNavOpen(false);
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [mobileNavOpen]);

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
      <style>{MOBILE_NAV_GLOBAL_STYLES}</style>

      {/* Sidebar fija con lista de MÓDULOS — full height para que el
          corner top-left de la pantalla pertenezca a la sidebar y no
          a un hueco del header. En <768px se transforma en drawer
          (slide-in desde la izquierda) controlado por `mobileNavOpen`. */}
      {activeModule && (
        <AppSidebar
          active={activeModule}
          mobileOpen={mobileNavOpen}
          onCloseMobile={() => setMobileNavOpen(false)}
        />
      )}

      {/* Backdrop del drawer mobile. Sólo se renderiza cuando está
          abierto; CSS lo oculta forzosamente en >=768px por si una
          transición de viewport lo deja visible. */}
      {mobileNavOpen && (
        <div
          data-mobile-backdrop="true"
          aria-hidden
          onClick={() => setMobileNavOpen(false)}
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.45)',
            zIndex: 45,
          }}
        />
      )}

      {/* Header fixed alineado con el contenido (empieza después de la
          sidebar). Así el corner sidebar-right ↔ header-bottom forma
          una L limpia en (240, 104). En mobile el `left` colapsa a 0
          vía media query. */}
      <header
        data-app-header="true"
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
          <IconButton
            ariaLabel="Abrir menú"
            onClick={() => setMobileNavOpen(true)}
            dataMobileOnly
            style={{ marginRight: 'auto' }}
          >
            <MenuIcon size={20} />
          </IconButton>
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
        data-app-main="true"
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
  dataMobileOnly,
  style,
}: {
  children: React.ReactNode;
  ariaLabel: string;
  onClick?: (() => void) | undefined;
  dataMobileOnly?: boolean;
  style?: React.CSSProperties;
}) {
  const [hovered, setHovered] = useState(false);
  return (
    <button
      type="button"
      aria-label={ariaLabel}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      {...(dataMobileOnly ? { 'data-mobile-only': 'true' } : {})}
      style={{
        // Cuando es mobile-only el default es 'none' y la media query
        // global lo eleva a 'inline-flex'. En el resto de IconButtons
        // se comporta como antes.
        display: dataMobileOnly ? 'none' : 'inline-flex',
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
        ...style,
      }}
    >
      {children}
    </button>
  );
}
