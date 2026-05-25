'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, type ComponentType } from 'react';

import type { AppModule, ModuleSection } from '@crisol/types';
import { colors, fontWeight, spacing } from '@crisol/ui';

import {
  ArrowLeftRightIcon,
  BarChart3Icon,
  ReceiptIcon,
  RepeatIcon,
  TargetIcon,
  type IconProps,
} from '@/components/ui/icons';

interface ModuleSectionsProps {
  module: AppModule;
  /**
   * Conteos opcionales por section key, para pintar el badge a la
   * derecha del label. Hoy se pasan desde el layout sólo cuando el
   * módulo activo es uno con queries baratas ya en memoria; cualquier
   * fetch nuevo aquí pagaría un round-trip por cada página, así que
   * preferimos enviar `undefined` y no pintar nada antes que añadir
   * un coste oculto al chrome.
   */
  counts?: Partial<Record<string, number>>;
}

// Icono por `section.key`. Mantenemos el mapeo aquí (no en el registry)
// para no acoplar `@crisol/types` al set de iconos de web.
const SECTION_ICONS: Record<string, ComponentType<IconProps>> = {
  analysis: BarChart3Icon,
  transactions: ReceiptIcon,
  budgets: TargetIcon,
  'fixed-expenses': RepeatIcon,
  transfers: ArrowLeftRightIcon,
};

/**
 * Tabs de secciones del módulo. PHASE-29.4 — añade iconos por section,
 * count badges opcionales y un subrayado copper 2px abajo para la
 * pestaña activa (más afín al lenguaje "tabs" que el pill que teníamos).
 */
export function ModuleSections({ module, counts }: ModuleSectionsProps) {
  const pathname = usePathname() ?? '';
  return (
    <ul
      style={{
        display: 'inline-flex',
        gap: spacing.xs,
        alignItems: 'center',
        margin: 0,
        padding: 0,
        listStyle: 'none',
        // El subrayado activo se ancla al `bottom: -1px` para "cortar"
        // sobre el borderBottom del header. Necesitamos overflow visible
        // explícito para que el pseudo no quede recortado.
        overflow: 'visible',
      }}
    >
      {module.sections.map((section) => {
        const active = pathname === section.path || pathname.startsWith(`${section.path}/`);
        const Icon = SECTION_ICONS[section.key];
        const count = counts?.[section.key];
        return (
          <li key={section.key} style={{ flex: '0 0 auto' }}>
            <SectionTab
              section={section}
              active={active}
              Icon={Icon}
              count={count}
            />
          </li>
        );
      })}
    </ul>
  );
}

function SectionTab({
  section,
  active,
  Icon,
  count,
}: {
  section: ModuleSection;
  active: boolean;
  Icon: ComponentType<IconProps> | undefined;
  count: number | undefined;
}) {
  const [hovered, setHovered] = useState(false);

  const filled = active || hovered;
  const bg = filled ? colors.surfaceMuted : 'transparent';
  const fg = active ? colors.text : hovered ? colors.text : colors.textMuted;
  const iconColor = filled ? colors.primary : colors.textMuted;
  const iconOpacity = filled ? 1 : 0.7;

  return (
    <Link
      href={section.path as never}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      aria-current={active ? 'page' : undefined}
      style={{
        position: 'relative',
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        padding: '7px 14px',
        borderRadius: 8,
        fontSize: 14,
        fontWeight: active ? fontWeight.semibold : fontWeight.medium,
        color: fg,
        backgroundColor: bg,
        textDecoration: 'none',
        transition: 'background-color 140ms ease, color 140ms ease',
        lineHeight: 1.4,
        whiteSpace: 'nowrap',
      }}
    >
      {Icon ? (
        <Icon
          size={14}
          style={{
            color: iconColor,
            opacity: iconOpacity,
            transition: 'color 140ms ease, opacity 140ms ease',
            flex: '0 0 auto',
          }}
        />
      ) : null}
      <span>{section.label}</span>
      {typeof count === 'number' ? (
        <span
          aria-hidden
          style={{
            display: 'inline-grid',
            placeItems: 'center',
            minWidth: 18,
            height: 18,
            padding: '0 5px',
            borderRadius: 999,
            backgroundColor: active ? colors.primarySoft : colors.surface,
            border: `1px solid ${active ? 'transparent' : colors.border}`,
            color: active ? colors.primary : colors.textMuted,
            fontSize: 10.5,
            fontWeight: fontWeight.semibold,
            fontVariantNumeric: 'tabular-nums',
            flex: '0 0 auto',
          }}
        >
          {count}
        </span>
      ) : null}
      {active ? (
        <span
          aria-hidden
          style={{
            position: 'absolute',
            left: 14,
            right: 14,
            bottom: -9,
            height: 2,
            backgroundColor: colors.primary,
            borderRadius: '1px 1px 0 0',
          }}
        />
      ) : null}
    </Link>
  );
}
