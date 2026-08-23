'use client';

import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { usePathname, useRouter } from 'next/navigation';

import { useAuthStore } from '@crisol/store';
import { authApi, useAccounts } from '@crisol/services';
import { DEFAULT_MODULE_ID, findModuleByPath, getModule } from '@crisol/types';
import { colors, spacing } from '@crisol/ui';

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
import { MenuIcon } from '@/components/ui/icons';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import { Toaster } from '@/components/ui/toaster';

// Estilos globales del drawer mobile. Se inyectan vía `<style>` porque
// el layout usa `style={{}}` inline (sin CSS modules ni Tailwind), y
// las inline styles ganan a las reglas CSS sin `!important`. Las
// reglas con `!important` aquí baten al inline `style` del layout
// para colapsar offsets de sidebar y mostrar/ocultar elementos
// `data-mobile-only` según el breakpoint.
const MOBILE_NAV_GLOBAL_STYLES = `
  .crisol-skip-link {
    position: fixed;
    top: 8px;
    left: 8px;
    z-index: 200;
    padding: 8px 16px;
    border-radius: 8px;
    background: var(--color-primary, #c4671f);
    color: var(--color-on-primary, #fff8f0);
    font-size: 14px;
    font-weight: 600;
    text-decoration: none;
    transform: translateY(-150%);
    transition: transform 140ms ease;
  }
  .crisol-skip-link:focus {
    transform: translateY(0);
    outline: 2px solid var(--color-primary, #c4671f);
    outline-offset: 2px;
  }
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
  const queryClient = useQueryClient();
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
      /*
       * PHASE-47 — vaciar el caché de queries al cerrar sesión.
       *
       * Las query keys no llevan la identidad del usuario (`['auth','me']` es
       * literalmente estática), así que sin esto el siguiente usuario que
       * entre en la misma pestaña hereda las respuestas del anterior mientras
       * duren sus `staleTime`. Con el perfil eso significa heredar su día de
       * corte: la app le pide sus datos «por ciclo» sin que él haya declarado
       * ninguno, y el servidor responde 422 en el endpoint que gobierna la
       * pantalla entera.
       *
       * Se limpia TODO y no sólo el perfil: el resto del caché son sus
       * transacciones y sus saldos, y tampoco tienen por qué sobrevivir a un
       * cierre de sesión.
       */
      queryClient.clear();
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

      {/* Skip-link: primer elemento focusable; salta directo al
          contenido principal sin tabular por toda la chrome
          (AUDIT-2026-05). Visualmente oculto hasta recibir foco. */}
      <a href="#main-content" className="crisol-skip-link">
        Saltar al contenido
      </a>

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
            gap: 6,
            padding: `0 16px 0 ${spacing.lg}px`,
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
          {/* PHASE-29.7: campana ocultada — no hay canal de
              notificaciones todavía. El botón + el dot se mantienen
              comentados en el código para reactivar trivialmente
              cuando el canal exista (ver `hasUnread` futuro). */}
          <CurrencyMenu />
          <ThemeToggle />
          <HeaderDivider />
          <UserMenu user={user} onLogout={handleLogout} />
        </div>

        {hasSections && (
          <nav
            aria-label="Secciones del módulo"
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
          </nav>
        )}
      </header>

      <main
        id="main-content"
        tabIndex={-1}
        data-app-main="true"
        style={{
          paddingTop: hasSections ? HEADER_HEIGHT : HEADER_HEIGHT_BARE,
          paddingLeft: SIDEBAR_WIDTH,
          minHeight: '100vh',
          boxSizing: 'border-box',
          outline: 'none',
        }}
      >
        <PasskeyPrompt />
        <AccountsGuard>{children}</AccountsGuard>
      </main>

      <Toaster />
    </div>
  );
}

/**
 * PHASE-19.1: bloquea el render del módulo hasta confirmar que el
 * usuario tiene al menos una cuenta. Si la lista está vacía empuja a
 * `/onboarding/accounts`. Vive en un sub-componente para que `useAccounts`
 * sólo se monte cuando el bootstrap de auth ya pasó (el padre devuelve
 * `null` antes de eso, así que aquí siempre hay sesión).
 */
function AccountsGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname() ?? '';
  const { data, isLoading, isError } = useAccounts();

  // PHASE-44.7 — Inversión es un espacio separado que no depende de las cuentas
  // de Finanzas Domésticas (decisión del usuario: sin reconciliar todavía). Se
  // exime del guard para que sea accesible sin cuenta de finanzas personales.
  const exempt = pathname.startsWith('/investments');

  useEffect(() => {
    if (exempt || isLoading) return;
    // Si la query falla (red caída, 5xx) no redirigimos — sería peor
    // dejar al usuario atrapado en onboarding. El children pintará su
    // propio estado de error.
    if (isError) return;
    if ((data ?? []).length === 0) {
      router.replace('/onboarding/accounts');
    }
  }, [data, isError, isLoading, router, exempt]);

  if (exempt) return <>{children}</>;
  // Mientras la query no resuelve no pintamos children — evita el flash
  // del módulo vacío antes de redirigir al onboarding.
  if (isLoading) return null;
  if (!isError && (data ?? []).length === 0) return null;
  return <>{children}</>;
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
  const [pressed, setPressed] = useState(false);
  return (
    <button
      type="button"
      aria-label={ariaLabel}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => {
        setHovered(false);
        setPressed(false);
      }}
      onMouseDown={() => setPressed(true)}
      onMouseUp={() => setPressed(false)}
      {...(dataMobileOnly ? { 'data-mobile-only': 'true' } : {})}
      style={{
        position: 'relative',
        display: dataMobileOnly ? 'none' : 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 36,
        height: 36,
        // PHASE-29.3: hover copper (era text neutro). Glow tonal via
        // bg `surface-muted`. Active press: scale .94.
        backgroundColor: hovered ? colors.surfaceMuted : 'transparent',
        color: hovered ? colors.primary : colors.textMuted,
        border: 'none',
        borderRadius: 8,
        cursor: 'pointer',
        transform: pressed ? 'scale(.94)' : 'scale(1)',
        transition:
          'background-color 140ms ease, color 140ms ease, transform 90ms ease',
        ...style,
      }}
    >
      {children}
    </button>
  );
}

/** Línea vertical 1×24 que separa grupos de controles en el header. */
function HeaderDivider() {
  return (
    <span
      aria-hidden
      style={{
        display: 'inline-block',
        width: 1,
        height: 24,
        backgroundColor: colors.border,
        margin: '0 4px',
        flex: '0 0 auto',
      }}
    />
  );
}
