'use client';

import type { CSSProperties } from 'react';

import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

export interface SegmentedOption {
  key: string;
  label: string;
  /** Se pinta apagada y con `title`, pero sigue siendo seleccionable: el
   *  usuario tiene derecho a abrirla y leer por qué está vacía. */
  degraded?: boolean | undefined;
  degradedHint?: string | undefined;
}

export interface SegmentedProps {
  options: SegmentedOption[];
  value: string;
  onChange: (key: string) => void;
  /** Nombre accesible del grupo. */
  label: string;
  size?: 'sm' | 'md';
}

/**
 * Control segmentado de segundo nivel (sub-secciones dentro de una pestaña).
 *
 * Existe porque el repo tenía cuatro `role="tablist"` escritos a mano en sitios
 * distintos, cada uno con su propio manejo de teclado (o sin ninguno).
 */
export function Segmented({ options, value, onChange, label, size = 'md' }: SegmentedProps) {
  return (
    <div
      role="group"
      aria-label={label}
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: spacing.xs,
        backgroundColor: colors.surfaceMuted,
        borderRadius: radius.md,
        padding: spacing.xs,
      }}
    >
      {options.map((option) => {
        const selected = option.key === value;
        return (
          <button
            key={option.key}
            type="button"
            aria-pressed={selected}
            onClick={() => onChange(option.key)}
            title={option.degraded ? option.degradedHint : undefined}
            style={segmentStyle(selected, size, Boolean(option.degraded))}
          >
            {option.label}
            {option.degraded ? <span aria-hidden> ○</span> : null}
          </button>
        );
      })}
    </div>
  );
}

function segmentStyle(selected: boolean, size: 'sm' | 'md', degraded: boolean): CSSProperties {
  return {
    background: selected ? colors.surface : 'transparent',
    border: 'none',
    borderRadius: radius.sm,
    boxShadow: selected ? `0 1px 2px ${colors.border}` : 'none',
    color: selected ? colors.text : degraded ? colors.textSubtle : colors.textMuted,
    fontSize: size === 'sm' ? fontSize.xs : fontSize.sm,
    fontWeight: selected ? fontWeight.semibold : fontWeight.medium,
    padding: `${spacing.xs}px ${spacing.md}px`,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  };
}
