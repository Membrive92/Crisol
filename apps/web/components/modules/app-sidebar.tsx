'use client';

import Link from 'next/link';
import { useState, type ComponentType } from 'react';

import { MODULES, type AppModule, type ModuleId } from '@crisol/types';
import { colors, fontWeight, spacing } from '@crisol/ui';

import {
  BarChart3Icon,
  HeartPulseIcon,
  HomeIcon,
  LayoutDashboardIcon,
  PlusIcon,
  TrendingUpIcon,
  WalletIcon,
  XIcon,
  type IconProps,
} from '@/components/ui/icons';

export const SIDEBAR_WIDTH = 240;
export const HEADER_ROW = 56;
export const TABS_ROW = 48;
export const HEADER_HEIGHT = HEADER_ROW + TABS_ROW; // con tabs (módulos con sections)
export const HEADER_HEIGHT_BARE = HEADER_ROW; // sin tabs (módulos planos como Dashboard)

// Breakpoint single source of truth para el drawer mobile. El layout
// inyecta media queries con este mismo valor — si cambia, actualizar
// también `MOBILE_NAV_GLOBAL_STYLES` en `(app)/layout.tsx`.
export const MOBILE_BREAKPOINT_PX = 768;

// PHASE-29.2: icono por módulo. Los módulos del registry no llevan icono
// todavía (ver TODO en `packages/types/src/models/module.ts`) — lo
// resolvemos aquí mientras tanto para no acoplar el shape del modelo al
// chrome web.
const MODULE_ICONS: Record<ModuleId, ComponentType<IconProps>> = {
  dashboard: LayoutDashboardIcon,
  'personal-finance': WalletIcon,
  debt: HeartPulseIcon,
  crypto: BarChart3Icon,
  investments: TrendingUpIcon,
  'real-estate': HomeIcon,
};

interface AppSidebarProps {
  active: AppModule;
  /** Estado del drawer mobile. En desktop (>=768px) este flag es ignorado por CSS. */
  mobileOpen?: boolean;
  /** Handler del botón "cerrar" interno de la sidebar (sólo visible en mobile). */
  onCloseMobile?: (() => void) | undefined;
}

/**
 * Sidebar lateral fija con la lista de **módulos** del producto.
 *
 * PHASE-29.2 — refactor del chrome:
 *  - Brand: logo (radial-gradient inline, no bitmap) + "Crisol" 17px / 600.
 *  - Items: padding generoso (10×12), gap 12, font 14 / 500, con
 *    ico-wrap 30×30 (radius 7) en `surface-muted` que se llena de
 *    `primary-soft` + copper al hover/active. La activa lleva un
 *    `::before` de 3px copper en el borde izquierdo (logrado vía un
 *    `<span>` absolutamente posicionado porque no usamos CSS modules).
 *  - Categorías: overline "ESPACIO" + "PRÓXIMAMENTE" para separar los
 *    módulos disponibles de los locked. Eliminado el `module-switcher`
 *    chip bajo el logo que duplicaba "Espacio".
 *  - CTA "Añadir transacción": gradient copper, 3 cols (plus + label
 *    con subtítulo + kbd "N"), el plus rota 90° en hover.
 *  - Footer: "Datos en este dispositivo" como caption para reforzar la
 *    privacy stance.
 */
export function AppSidebar({ active, mobileOpen = false, onCloseMobile }: AppSidebarProps) {
  const enabled = MODULES.filter((m) => m.enabled);
  const locked = MODULES.filter((m) => !m.enabled);

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
        backgroundColor: colors.background,
        borderRight: `1px solid ${colors.border}`,
        display: 'flex',
        flexDirection: 'column',
        zIndex: 60,
      }}
    >
      {/* Brand */}
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
            gap: 10,
            fontSize: 17,
            fontWeight: fontWeight.semibold,
            color: colors.text,
            letterSpacing: '-0.01em',
          }}
        >
          <BrandDot />
          Crisol
        </span>
        <button
          type="button"
          data-mobile-only="true"
          aria-label="Cerrar menú"
          onClick={onCloseMobile}
          style={{
            display: 'none',
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

      {/* Módulos disponibles + próximos */}
      <nav
        aria-label="Módulos"
        style={{
          padding: `${spacing.md}px ${spacing.md}px 0`,
          display: 'flex',
          flexDirection: 'column',
          gap: spacing.md,
        }}
      >
        <Section title="Espacio">
          {enabled.map((m) => (
            <ModuleItem key={m.id} module={m} isActive={m.id === active.id} />
          ))}
        </Section>

        {locked.length > 0 ? (
          <Section title="Próximamente">
            {locked.map((m) => (
              <ModuleItem key={m.id} module={m} isActive={false} />
            ))}
          </Section>
        ) : null}
      </nav>

      <div style={{ flex: 1 }} />

      {/* Footer: CTA + caption */}
      <div style={{ padding: spacing.md, borderTop: `1px solid ${colors.border}` }}>
        <PrimaryCTA />
        <p
          style={{
            margin: `${spacing.sm}px 0 0`,
            fontSize: 11,
            color: colors.textSubtle,
            textAlign: 'center',
            letterSpacing: '0.02em',
          }}
        >
          Datos en este dispositivo
        </p>
      </div>
    </aside>
  );
}

/* ---------- helpers internos ---------- */

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p
        style={{
          margin: `0 ${spacing.sm + 4}px ${spacing.xs}px`,
          fontSize: 10.5,
          fontWeight: fontWeight.semibold,
          color: colors.textSubtle,
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
        }}
      >
        {title}
      </p>
      <ul
        style={{
          listStyle: 'none',
          margin: 0,
          padding: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
        }}
      >
        {children}
      </ul>
    </div>
  );
}

function ModuleItem({ module, isActive }: { module: AppModule; isActive: boolean }) {
  const [hovered, setHovered] = useState(false);
  const disabled = !module.enabled;
  const Icon = MODULE_ICONS[module.id];

  // Estado visual:
  //  - locked  → ico-wrap apagado (.55), chip "Pronto" a la derecha.
  //  - active  → ico-wrap copper-soft + copper icon, bar copper a la izq.
  //  - hovered → ico-wrap copper-soft + copper icon, sin bar.
  //  - normal  → ico-wrap surface-muted.
  const filled = (!disabled && (isActive || hovered));
  const wrapBg = filled ? colors.primarySoft : colors.surfaceMuted;
  const wrapFg = filled ? colors.primary : colors.textMuted;
  const wrapBorder = filled ? 'transparent' : colors.border;
  const itemBg = isActive || hovered ? colors.surfaceMuted : 'transparent';
  const itemFg = disabled
    ? colors.textSubtle
    : isActive
      ? colors.text
      : hovered
        ? colors.text
        : colors.textMuted;
  const itemWeight = isActive ? fontWeight.semibold : fontWeight.medium;

  const inner = (
    <>
      {/* Barra activa, posicionada a la izquierda del item. Sólo
          aparece cuando el item está activo — vivimos sin pseudo
          elementos porque usamos inline styles. */}
      {isActive ? (
        <span
          aria-hidden
          style={{
            position: 'absolute',
            left: -spacing.md + 2,
            top: 10,
            bottom: 10,
            width: 3,
            backgroundColor: colors.primary,
            borderRadius: '0 3px 3px 0',
          }}
        />
      ) : null}
      <span
        aria-hidden
        style={{
          width: 30,
          height: 30,
          borderRadius: 7,
          display: 'grid',
          placeItems: 'center',
          backgroundColor: wrapBg,
          color: wrapFg,
          border: `1px solid ${wrapBorder}`,
          flex: '0 0 auto',
          transition:
            'background-color 140ms ease, color 140ms ease, border-color 140ms ease',
          opacity: disabled ? 0.55 : 1,
        }}
      >
        {Icon ? <Icon size={16} /> : <span style={{ width: 8, height: 8 }} />}
      </span>
      <span
        style={{
          flex: 1,
          minWidth: 0,
          lineHeight: 1.2,
          // Sin estas tres reglas el label largo (ej. "Criptomonedas")
          // se desborda visualmente por encima del chip "Pronto", aunque
          // el chip tenga `flex: 0 0 auto`. El truncado evita el solape.
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {module.label}
      </span>
      {disabled ? <SoonChip /> : null}
    </>
  );

  const baseStyle: React.CSSProperties = {
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    padding: '10px 12px',
    borderRadius: 8,
    backgroundColor: itemBg,
    color: itemFg,
    fontSize: 14,
    fontWeight: itemWeight,
    textDecoration: 'none',
    transition: 'background-color 140ms ease, color 140ms ease',
  };

  if (disabled) {
    return (
      <li>
        <div
          aria-disabled
          style={{ ...baseStyle, cursor: 'not-allowed' }}
        >
          {inner}
        </div>
      </li>
    );
  }

  const target = module.sections[0]?.path ?? module.basePath;
  return (
    <li>
      <Link
        href={target as never}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        aria-current={isActive ? 'page' : undefined}
        style={{ ...baseStyle, cursor: 'pointer' }}
      >
        {inner}
      </Link>
    </li>
  );
}

function SoonChip() {
  return (
    <span
      aria-hidden
      style={{
        marginLeft: 4,
        fontSize: 9,
        fontWeight: fontWeight.semibold,
        color: colors.textSubtle,
        backgroundColor: 'transparent',
        border: `1px solid ${colors.border}`,
        padding: '1px 6px',
        borderRadius: 999,
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
        lineHeight: 1.4,
        flex: '0 0 auto',
        whiteSpace: 'nowrap',
      }}
    >
      Pronto
    </span>
  );
}

/**
 * Logo dot del sidebar: radial-gradient cobre, inline. Reemplaza el
 * favicon.svg en el chrome (el favicon sigue siendo el de la pestaña
 * del navegador). 24×24, radius 7.
 */
function BrandDot() {
  return (
    <span
      aria-hidden
      style={{
        position: 'relative',
        display: 'inline-block',
        width: 24,
        height: 24,
        borderRadius: 7,
        background:
          'radial-gradient(circle at 30% 30%, #ffb673 0%, #e07a3a 55%, #9a4a18 100%)',
        boxShadow:
          '0 0 0 1px rgba(224,122,58,.35), 0 0 16px rgba(224,122,58,.25), inset 0 1px 0 rgba(255,255,255,.35)',
        flex: '0 0 auto',
      }}
    >
      <span
        aria-hidden
        style={{
          position: 'absolute',
          inset: 4,
          borderRadius: 4,
          background:
            'radial-gradient(circle at 40% 35%, #ffe5c4, #e07a3a 70%)',
        }}
      />
    </span>
  );
}

/**
 * CTA "Añadir transacción": gradient copper, 3 columnas (plus + label
 * con subtítulo + kbd "N"). El icono `+` rota 90° en hover para
 * sugerir afordancia de "abrir". El atajo `n` aún no está cableado
 * (TODO listener global) — el kbd es honest signage de la intención.
 */
function PrimaryCTA() {
  const [hovered, setHovered] = useState(false);
  return (
    <Link
      href="/personal-finance/transactions/new"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        position: 'relative',
        width: '100%',
        // `border-box` para que el padding+border NO se sumen por
        // encima del 100% (content-box por defecto haría el botón
        // ~26px más ancho que la sidebar y se saldría por la derecha).
        boxSizing: 'border-box',
        display: 'grid',
        gridTemplateColumns: '30px 1fr auto',
        alignItems: 'center',
        gap: 10,
        padding: '10px 12px',
        borderRadius: 10,
        background: `linear-gradient(180deg, ${colors.primary} 0%, ${colors.primaryDark} 100%)`,
        color: colors.onPrimary,
        border: `1px solid ${colors.primaryDark}`,
        fontSize: 13.5,
        fontWeight: fontWeight.semibold,
        cursor: 'pointer',
        textDecoration: 'none',
        // Glow cobre más compacto: el `spread` negativo (-12/-14) y el
        // `blur` reducido evitan que el halo se desborde por el lado
        // derecho de la sidebar (la sidebar mide 240px y el contenedor
        // del footer ya recorta visualmente).
        boxShadow: hovered
          ? 'inset 0 1px 0 rgba(255,255,255,.22), 0 2px 4px rgba(0,0,0,.2), 0 6px 14px -10px rgba(196,103,31,.55)'
          : 'inset 0 1px 0 rgba(255,255,255,.22), 0 1px 2px rgba(0,0,0,.18), 0 4px 12px -14px rgba(196,103,31,.5)',
        filter: hovered ? 'brightness(1.08)' : 'none',
        transition: 'box-shadow 160ms ease, filter 160ms ease',
      }}
    >
      <span
        aria-hidden
        style={{
          width: 30,
          height: 30,
          borderRadius: 8,
          backgroundColor: 'rgba(0,0,0,.18)',
          display: 'grid',
          placeItems: 'center',
          color: colors.onPrimary,
          transform: hovered ? 'rotate(90deg)' : 'rotate(0deg)',
          transition: 'transform 200ms ease',
        }}
      >
        <PlusIcon size={14} />
      </span>
      <span
        style={{
          display: 'flex',
          flexDirection: 'column',
          textAlign: 'left',
          minWidth: 0,
          lineHeight: 1.15,
        }}
      >
        <span>Añadir transacción</span>
        <small
          style={{
            fontSize: 10.5,
            fontWeight: fontWeight.medium,
            opacity: 0.72,
            marginTop: 2,
          }}
        >
          Nuevo movimiento
        </small>
      </span>
      <span
        aria-hidden
        style={{
          minWidth: 22,
          padding: '2px 6px',
          borderRadius: 6,
          backgroundColor: 'rgba(0,0,0,.22)',
          fontSize: 11,
          fontWeight: fontWeight.bold,
          color: colors.onPrimary,
          textAlign: 'center',
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        N
      </span>
    </Link>
  );
}
