'use client';

import type { CategoryKind } from '@finanzas/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

export interface CategoryChipProps {
  /**
   * Nombre que se muestra en el chip. Si la categoría no existe, el
   * caller pasa "Sin categoría" y `kind={null}`.
   */
  label: string;
  /**
   * `kind` determina la paleta tonal. `null` representa el bucket de
   * "sin categoría" — pintado con el primario suave.
   */
  kind: CategoryKind | null;
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

/**
 * Chip tonal para categorías. Fondo `*-soft` (tinte por tema) +
 * foreground saturado. Tipografía `overline`. Pensado para tablas
 * (Transactions) y filas de listado donde la categoría es secundaria
 * al concepto.
 */
export function CategoryChip({ label, kind }: CategoryChipProps) {
  const palette = paletteFor(kind);
  return (
    <span
      style={{
        display: 'inline-block',
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
      {label}
    </span>
  );
}
