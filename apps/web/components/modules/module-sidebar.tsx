'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, type ComponentType } from 'react';

import { MODULES, type AppModule } from '@finanzas/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

import {
  ArrowLeftRightIcon,
  BarChart3Icon,
  LayoutDashboardIcon,
  LockIcon,
  PlusIcon,
  ReceiptIcon,
  SettingsIcon,
  UploadIcon,
} from '@/components/ui/icons';

// Anchura fija de la sidebar. Por encima de `lg` se empuja el contenido
// principal con `padding-left`; por debajo, la sidebar se oculta y el
// usuario navega desde un drawer (TODO: drawer mobile en una iteración
// posterior — por ahora sólo escondemos).
export const SIDEBAR_WIDTH = 240;

interface IconProps {
  size?: number | undefined;
}

type IconCmp = ComponentType<IconProps>;

const SECTION_ICONS: Record<string, IconCmp> = {
  dashboard: LayoutDashboardIcon,
  analysis: BarChart3Icon,
  transactions: ArrowLeftRightIcon,
  imports: UploadIcon,
  receipts: ReceiptIcon,
};

interface ModuleSidebarProps {
  active: AppModule;
}

/**
 * Sidebar fija de la app. Cabecera con el módulo activo y un punto
 * indicador. Lista de secciones con icono + label. Items de otros
 * módulos pintados deshabilitados con badge "Próximamente". Footer
 * con CTA "+ Añadir transacción".
 */
export function ModuleSidebar({ active }: ModuleSidebarProps) {
  const pathname = usePathname() ?? '';

  return (
    <aside
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        bottom: 0,
        width: SIDEBAR_WIDTH,
        backgroundColor: colors.surface,
        borderRight: `1px solid ${colors.border}`,
        display: 'flex',
        flexDirection: 'column',
        paddingTop: 64, // hueco para el top header sticky
        zIndex: 40,
      }}
    >
      {/* Header del módulo activo */}
      <div style={{ padding: `${spacing.md}px ${spacing.md}px ${spacing.sm}px` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm, marginBottom: 4 }}>
          <span
            aria-hidden
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: colors.primary,
              flex: '0 0 auto',
            }}
          />
          <span
            style={{
              fontSize: fontSize.md,
              fontWeight: fontWeight.semibold,
              color: colors.text,
            }}
          >
            {active.label}
          </span>
        </div>
        <span
          style={{
            display: 'block',
            paddingLeft: 8 + spacing.sm,
            fontSize: fontSize.xs,
            color: colors.textSubtle,
          }}
        >
          Local-first
        </span>
      </div>

      {/* Secciones del módulo activo */}
      <nav
        aria-label="Secciones del módulo"
        style={{ padding: `0 ${spacing.sm}px`, marginBottom: spacing.md }}
      >
        <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
          {active.sections.map((section) => {
            const isActive =
              pathname === section.path || pathname.startsWith(`${section.path}/`);
            const SectionIcon = SECTION_ICONS[section.key] ?? LayoutDashboardIcon;
            return (
              <li key={section.key}>
                <SidebarItem
                  href={section.path}
                  label={section.label}
                  Icon={SectionIcon}
                  active={isActive}
                />
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Otros módulos (deshabilitados) */}
      <div style={{ padding: `0 ${spacing.md}px ${spacing.sm}px` }}>
        <span
          style={{
            display: 'block',
            fontSize: fontSize.xs,
            fontWeight: fontWeight.semibold,
            color: colors.textSubtle,
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
          }}
        >
          Otros módulos
        </span>
      </div>
      <ul
        style={{
          listStyle: 'none',
          margin: 0,
          padding: `0 ${spacing.sm}px`,
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
          marginBottom: spacing.md,
        }}
      >
        {MODULES.filter((m) => m.id !== active.id).map((m) => (
          <li key={m.id}>
            <DisabledModuleRow module={m} />
          </li>
        ))}
      </ul>

      <div style={{ flex: 1 }} />

      {/* Footer: ajustes + CTA */}
      <div style={{ padding: `${spacing.sm}px ${spacing.sm}px` }}>
        <SidebarItem
          href="/settings"
          label="Ajustes"
          Icon={SettingsIcon}
          active={pathname.startsWith('/settings')}
        />
      </div>
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

function SidebarItem({
  href,
  label,
  Icon,
  active,
}: {
  href: string;
  label: string;
  Icon: IconCmp;
  active: boolean;
}) {
  const [hovered, setHovered] = useState(false);

  const bg = active ? colors.surfaceMuted : hovered ? colors.surfaceMuted : 'transparent';
  const fg = active ? colors.primary : colors.textMuted;
  const borderRight = active ? `2px solid ${colors.primary}` : '2px solid transparent';

  return (
    <Link
      href={href as never}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      aria-current={active ? 'page' : undefined}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: spacing.sm,
        padding: `${spacing.sm}px ${spacing.sm + 4}px`,
        backgroundColor: bg,
        color: fg,
        borderRadius: radius.md,
        borderRight,
        fontSize: fontSize.sm,
        fontWeight: active ? fontWeight.semibold : fontWeight.medium,
        textDecoration: 'none',
        lineHeight: 1.2,
        transition: 'background-color 120ms ease, color 120ms ease',
      }}
    >
      <Icon size={18} />
      <span>{label}</span>
    </Link>
  );
}

function DisabledModuleRow({ module }: { module: AppModule }) {
  return (
    <div
      aria-disabled
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: spacing.sm,
        padding: `${spacing.sm}px ${spacing.sm + 4}px`,
        backgroundColor: 'transparent',
        color: colors.textSubtle,
        borderRadius: radius.md,
        fontSize: fontSize.sm,
        fontWeight: fontWeight.medium,
        cursor: 'not-allowed',
        opacity: 0.7,
      }}
    >
      <LockIcon size={18} />
      <span style={{ flex: 1 }}>{module.label}</span>
      <span
        style={{
          fontSize: fontSize.xs,
          fontWeight: fontWeight.semibold,
          color: colors.textSubtle,
        }}
      >
        Pronto
      </span>
    </div>
  );
}
