'use client';

import type { CategoryKind } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

export interface CategoryChipProps {
  /**
   * Nombre que se muestra en el chip. Si la categoría no existe, el
   * caller pasa "Sin categoría" y `kind={null}`.
   */
  label: string;
  /**
   * `kind` determina la paleta de fallback. `null` representa el bucket
   * de "sin categoría" — pintado con el primario suave.
   */
  kind: CategoryKind | null;
  /** Hex `#RRGGBB` propio de la categoría — gana sobre la paleta por kind. */
  color?: string | null;
  /** Emoji prefix opcional (ej. "🍽️"). */
  icon?: string | null;
}

interface Palette {
  bg: string;
  fg: string;
}

function paletteFor(kind: CategoryKind | null): Palette {
  if (kind === 'income') {
    return { bg: colors.successSoft, fg: colors.success };
  }
  if (kind === 'expense') {
    return { bg: colors.dangerSoft, fg: colors.danger };
  }
  return { bg: colors.primarySoft, fg: colors.primary };
}

function hexToRgba(hex: string, alpha: number): string | null {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return null;
  const v = m[1]!;
  const r = parseInt(v.slice(0, 2), 16);
  const g = parseInt(v.slice(2, 4), 16);
  const b = parseInt(v.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function paletteForColor(color: string): Palette {
  const bg = hexToRgba(color, 0.15);
  if (bg === null) return paletteFor(null);
  return { bg, fg: color };
}

/**
 * Chip tonal para categorías. Si `color` está definido, usa una versión
 * tintada del hex como fondo y el hex como foreground. Si no, cae a la
 * paleta por `kind`.
 */
export function CategoryChip({ label, kind, color, icon }: CategoryChipProps) {
  const palette = color ? paletteForColor(color) : paletteFor(kind);
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        padding: `${spacing.xs / 2}px ${spacing.sm}px`,
        backgroundColor: palette.bg,
        color: palette.fg,
        borderRadius: radius.sm,
        fontSize: fontSize.xs,
        fontWeight: fontWeight.semibold,
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
        whiteSpace: 'nowrap',
      }}
    >
      {icon ? (
        <span aria-hidden="true" style={{ textTransform: 'none', fontSize: fontSize.sm }}>
          {icon}
        </span>
      ) : null}
      <span>{label}</span>
    </span>
  );
}
