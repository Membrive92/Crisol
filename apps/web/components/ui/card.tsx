'use client';

import type { CSSProperties, HTMLAttributes, ReactNode } from 'react';

import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /**
   * PHASE-38 — Padding compacto (`spacing.md`, 16px) para cards densas cuyo
   * contenido se vería vacío con el padding roomier: KPI tiles, filas de
   * lista, tarjetas de tip. Por defecto las cards de contenido usan
   * `spacing.lg` (24px), alineado con la vista de Análisis. Un `padding`
   * explícito en `style` sigue ganando (p. ej. `padding: 0` en contenedores
   * de lista).
   */
  compact?: boolean;
}

/**
 * Card base de la app. PHASE-38 estandariza el padding roomier (`lg`) como
 * defecto — antes era `md` y cada card de Análisis lo sobreescribía a `lg`
 * inline. Las cards compactas pasan `compact`. Fuente única del "look" de
 * card (superficie, borde, radio, padding).
 */
export function Card({ compact, style, ...rest }: CardProps) {
  return (
    <div
      {...rest}
      style={{
        // `border-box` para que `height: 100%` (cards que se estiran en un
        // grid) incluya el padding y el borde. Sin esto (content-box, el
        // default, no hay reset global) una card `height:100%` mide
        // celda + 2×padding + borde y DESBORDA ~50px sobre la card de abajo,
        // solapando su cabecera.
        boxSizing: 'border-box',
        backgroundColor: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.md,
        padding: compact ? spacing.md : spacing.lg,
        ...style,
      }}
    />
  );
}

/**
 * PHASE-38 — Título de card consistente (`h3`). Unifica la tipografía de
 * cabecera, que antes era ad-hoc por card (unas a `fontSize.lg`, otras `md`).
 * `size="sm"` para sub-secciones dentro de una card.
 */
export function CardTitle({
  children,
  size = 'md',
  style,
  ...rest
}: {
  children: ReactNode;
  size?: 'md' | 'sm';
  style?: CSSProperties;
} & Omit<HTMLAttributes<HTMLHeadingElement>, 'style'>) {
  return (
    <h3
      {...rest}
      style={{
        margin: 0,
        fontSize: size === 'sm' ? fontSize.md : fontSize.lg,
        fontWeight: fontWeight.semibold,
        color: colors.text,
        letterSpacing: '-0.01em',
        lineHeight: 1.2,
        ...style,
      }}
    >
      {children}
    </h3>
  );
}
