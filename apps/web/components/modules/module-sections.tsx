'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';

import type { AppModule, ModuleSection } from '@finanzas/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

interface ModuleSectionsProps {
  module: AppModule;
}

/**
 * Tabs de secciones del módulo. Pensado para vivir inline en el
 * header de la app: sin wrapping (el padre maneja overflow-x), gap
 * ajustado y sin barra inferior — el activo se marca con bg pill +
 * texto fuerte, ya que el `borderBottom` del header ya cierra la fila.
 */
export function ModuleSections({ module }: ModuleSectionsProps) {
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
      }}
    >
      {module.sections.map((section) => {
        const active = pathname === section.path || pathname.startsWith(`${section.path}/`);
        return (
          <li key={section.key} style={{ flex: '0 0 auto' }}>
            <SectionTab section={section} active={active} />
          </li>
        );
      })}
    </ul>
  );
}

function SectionTab({ section, active }: { section: ModuleSection; active: boolean }) {
  const [hovered, setHovered] = useState(false);

  // Activo → tinte primario (`primary-soft` bg + `primary` text). Hover
  // sin azul (`surface`) para diferenciar del estado activo. Inactivo
  // muted.
  const bg = active
    ? colors.primarySoft
    : hovered
      ? colors.surface
      : 'transparent';
  const fg = active ? colors.primary : hovered ? colors.text : colors.textMuted;

  return (
    <Link
      href={section.path as never}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      aria-current={active ? 'page' : undefined}
      style={{
        display: 'inline-block',
        padding: `${spacing.xs}px ${spacing.sm + 4}px`,
        borderRadius: radius.md,
        fontSize: fontSize.sm,
        fontWeight: active ? fontWeight.semibold : fontWeight.medium,
        color: fg,
        backgroundColor: bg,
        textDecoration: 'none',
        transition: 'background-color 120ms ease, color 120ms ease',
        lineHeight: 1.3,
        whiteSpace: 'nowrap',
      }}
    >
      {section.label}
    </Link>
  );
}
