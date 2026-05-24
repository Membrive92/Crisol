'use client';

import Link from 'next/link';
import { useState } from 'react';

import { MODULES, type AppModule } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

import { LockIcon, PlusIcon, XIcon } from '@/components/ui/icons';

export const SIDEBAR_WIDTH = 240;
export const HEADER_ROW = 56;
export const TABS_ROW = 48;
export const HEADER_HEIGHT = HEADER_ROW + TABS_ROW; // con tabs (módulos con sections)
export const HEADER_HEIGHT_BARE = HEADER_ROW; // sin tabs (módulos planos como Dashboard)

// Breakpoint single source of truth para el drawer mobile. El layout
// inyecta media queries con este mismo valor — si cambia, actualizar
// también `MOBILE_NAV_GLOBAL_STYLES` en `(app)/layout.tsx`.
export const MOBILE_BREAKPOINT_PX = 768;

interface AppSidebarProps {
  active: AppModule;
  /** Estado del drawer mobile. En desktop (>=768px) este flag es ignorado por CSS. */
  mobileOpen?: boolean;
  /** Handler del botón "cerrar" interno de la sidebar (sólo visible en mobile). */
  onCloseMobile?: (() => void) | undefined;
}

/**
 * Sidebar lateral fija con la lista de **módulos** del producto.
 * El módulo activo se marca con dot + bg `surfaceMuted` + border-right
 * en `primary`. Los demás módulos del registro (`crypto`,
 * `investments`, `real-estate`) aparecen deshabilitados con caption
 * "Próximamente". Footer con CTA "+ Añadir transacción".
 *
 * Las secciones internas del módulo activo (Dashboard, Análisis,
 * etc.) NO viven aquí — viven en la barra superior, vía
 * `<ModuleSections>`.
 */
export function AppSidebar({ active, mobileOpen = false, onCloseMobile }: AppSidebarProps) {
  return (
    <aside
      data-app-sidebar="true"
      data-mobile-open={mobileOpen ? 'true' : 'false'}
      aria-hidden={undefined}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        bottom: 0,
        width: SIDEBAR_WIDTH,
        // Chrome dark: el panel lateral se asienta en `background`, no
        // `surface`. Las cards del contenido principal usan `surface`,
        // así que se elevan visualmente sobre el chrome — patrón
        // típico de UIs dark mode (Linear, Vercel, Stitch).
        backgroundColor: colors.background,
        borderRight: `1px solid ${colors.border}`,
        display: 'flex',
        flexDirection: 'column',
        // Sube por encima del header (50) y backdrop (45) para que en
        // modo drawer cubra el chrome al deslizarse. En desktop no
        // entra en conflicto porque sidebar y header no se solapan.
        zIndex: 60,
      }}
    >
      {/* Marca — único bloque de branding de la sidebar. Vive en el
          top-left para que el corner superior pertenezca al panel
          lateral y no a un hueco del header. La caption "Workspace ·
          Almacenamiento local" se eliminó: era ruido sin información
          accionable. */}
      <div
        style={{
          height: 56,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: `0 ${spacing.lg}px`,
          borderBottom: `1px solid ${colors.border}`,
          flex: '0 0 auto',
        }}
      >
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: spacing.sm,
            fontSize: fontSize.lg,
            fontWeight: fontWeight.bold,
            color: colors.text,
            letterSpacing: '-0.02em',
          }}
        >
          <img
            src="/favicon.svg"
            alt=""
            aria-hidden="true"
            width={24}
            height={24}
            style={{ display: 'block', flex: '0 0 auto' }}
          />
          Crisol
        </span>
        <button
          type="button"
          data-mobile-only="true"
          aria-label="Cerrar menú"
          onClick={onCloseMobile}
          style={{
            display: 'none', // override en mobile vía media query global
            alignItems: 'center',
            justifyContent: 'center',
            width: 36,
            height: 36,
            backgroundColor: 'transparent',
            color: colors.textMuted,
            border: 'none',
            borderRadius: 8,
            cursor: 'pointer',
            padding: 0,
          }}
        >
          <XIcon size={20} />
        </button>
      </div>

      {/* Lista de módulos */}
      <nav
        aria-label="Módulos"
        style={{ padding: `${spacing.md}px ${spacing.sm}px 0`, marginBottom: spacing.md }}
      >
        <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
          {MODULES.map((m) => (
            <li key={m.id}>
              <ModuleRow module={m} isActive={m.id === active.id} />
            </li>
          ))}
        </ul>
      </nav>

      <div style={{ flex: 1 }} />

      {/* Footer: CTA */}
      <div style={{ padding: spacing.md, borderTop: `1px solid ${colors.border}` }}>
        <Link
          href="/personal-finance/transactions/new"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: spacing.xs,
            width: '100%',
            padding: `${spacing.sm + 2}px 0`,
            backgroundColor: colors.primary,
            color: colors.onPrimary,
            border: `1px solid ${colors.primary}`,
            borderRadius: radius.md,
            fontSize: fontSize.sm,
            fontWeight: fontWeight.semibold,
            textDecoration: 'none',
          }}
        >
          <PlusIcon size={16} />
          Añadir transacción
        </Link>
      </div>
    </aside>
  );
}

function ModuleRow({ module, isActive }: { module: AppModule; isActive: boolean }) {
  const [hovered, setHovered] = useState(false);
  const disabled = !module.enabled;

  // Item activo (módulo en el que está el usuario): bg + border-right
  // primary + texto strong + dot primary.
  // Items habilitados pero no activos: link estándar — no aplica
  // todavía (el MVP sólo tiene personal-finance habilitado).
  // Items deshabilitados: bg neutro, color subtle, no clicables.

  if (disabled) {
    return (
      <div
        aria-disabled
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: spacing.sm,
          padding: `${spacing.sm + 2}px ${spacing.sm + 4}px`,
          backgroundColor: 'transparent',
          color: colors.textSubtle,
          borderRadius: radius.md,
          fontSize: fontSize.sm,
          fontWeight: fontWeight.medium,
          cursor: 'not-allowed',
          opacity: 0.7,
        }}
      >
        <LockIcon size={16} />
        <span style={{ flex: 1 }}>{module.label}</span>
        <span
          style={{
            fontSize: 11,
            fontWeight: fontWeight.semibold,
            color: colors.textSubtle,
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
          }}
        >
          Pronto
        </span>
      </div>
    );
  }

  // Habilitado — link al primer section o basePath.
  const target = module.sections[0]?.path ?? module.basePath;
  // Activo → bg `primary-soft` (azul tinte) + texto y borde primarios.
  // Hover → `surface` (un escalón por encima del chrome) sin azul para
  // diferenciarlo del estado activo.
  const bg = isActive ? colors.primarySoft : hovered ? colors.surface : 'transparent';
  const fg = isActive ? colors.primary : colors.text;
  const borderRight = isActive ? `2px solid ${colors.primary}` : '2px solid transparent';

  return (
    <Link
      href={target as never}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      aria-current={isActive ? 'page' : undefined}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: spacing.sm,
        padding: `${spacing.sm + 2}px ${spacing.sm + 4}px`,
        backgroundColor: bg,
        color: fg,
        borderRadius: radius.md,
        borderRight,
        fontSize: fontSize.sm,
        fontWeight: isActive ? fontWeight.semibold : fontWeight.medium,
        textDecoration: 'none',
        lineHeight: 1.2,
        transition: 'background-color 120ms ease, color 120ms ease',
      }}
    >
      <span
        aria-hidden
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          backgroundColor: isActive ? colors.primary : colors.borderStrong,
          flex: '0 0 auto',
        }}
      />
      <span>{module.label}</span>
    </Link>
  );
}
