'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';

import type { AppModule, ModuleSection } from '@finanzas/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

interface ModuleSectionsProps {
  module: AppModule;
}

export function ModuleSections({ module }: ModuleSectionsProps) {
  const pathname = usePathname() ?? '';
  return (
    <nav
      aria-label="Secciones del módulo"
      style={{
        display: 'flex',
        gap: spacing.xs,
        alignItems: 'center',
        flexWrap: 'wrap',
      }}
    >
      {module.sections.map((section) => {
        const active = pathname === section.path || pathname.startsWith(`${section.path}/`);
        return <SectionTab key={section.key} section={section} active={active} />;
      })}
    </nav>
  );
}

function SectionTab({ section, active }: { section: ModuleSection; active: boolean }) {
  const [hovered, setHovered] = useState(false);

  const bg = active
    ? colors.surfaceMuted
    : hovered
      ? colors.surfaceMuted
      : 'transparent';
  const fg = active ? colors.text : hovered ? colors.text : colors.textMuted;

  return (
    <Link
      href={section.path as never}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      aria-current={active ? 'page' : undefined}
      style={{
        position: 'relative',
        padding: `${spacing.xs + 2}px ${spacing.sm + 4}px`,
        borderRadius: radius.md,
        fontSize: fontSize.sm,
        fontWeight: active ? fontWeight.semibold : fontWeight.medium,
        color: fg,
        backgroundColor: bg,
        textDecoration: 'none',
        transition: 'background-color 120ms ease, color 120ms ease',
        lineHeight: 1.2,
      }}
    >
      {section.label}
      {active ? (
        <span
          aria-hidden
          style={{
            position: 'absolute',
            left: spacing.sm + 4,
            right: spacing.sm + 4,
            bottom: -1,
            height: 2,
            borderRadius: 2,
            backgroundColor: colors.primary,
          }}
        />
      ) : null}
    </Link>
  );
}
