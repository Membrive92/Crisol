'use client';

import Link, { type LinkProps } from 'next/link';
import type { ButtonHTMLAttributes, CSSProperties, ReactNode } from 'react';

import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';

const baseStyle: CSSProperties = {
  position: 'fixed',
  right: spacing.lg,
  bottom: spacing.lg,
  width: 56,
  height: 56,
  borderRadius: 9999,
  backgroundColor: colors.primary,
  color: colors.onPrimary,
  border: 'none',
  cursor: 'pointer',
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontSize: fontSize.xl,
  fontWeight: fontWeight.bold,
  // Sombra fuerte porque vive sobre cualquier surface; en light el shadow
  // de elevation.overlay es demasiado denso, así que afinamos aquí.
  boxShadow: '0 8px 24px rgba(0, 0, 0, 0.32)',
  zIndex: 30,
  lineHeight: 1,
};

export interface FabButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Etiqueta accesible cuando el contenido visual sea sólo un icono. */
  ariaLabel: string;
  children?: ReactNode;
}

/**
 * Botón flotante circular para CTA contextual de pantalla. Pintado con
 * `primary` filled. Posición fixed bottom-right por defecto; el caller
 * puede sobrescribir con `style` si hace falta moverlo (p. ej. encima
 * de un bottom-sheet).
 */
export function FabButton({ ariaLabel, style, children, ...rest }: FabButtonProps) {
  return (
    <button
      type="button"
      aria-label={ariaLabel}
      {...rest}
      style={{ ...baseStyle, ...style }}
    >
      {children ?? '+'}
    </button>
  );
}

export interface FabLinkProps extends Omit<LinkProps, 'children'> {
  ariaLabel: string;
  children?: ReactNode;
  style?: CSSProperties | undefined;
}

/** Variante de FAB que navega en lugar de disparar un onClick. */
export function FabLink({ ariaLabel, style, children, ...rest }: FabLinkProps) {
  return (
    <Link
      aria-label={ariaLabel}
      {...rest}
      style={{ ...baseStyle, textDecoration: 'none', ...style }}
    >
      {children ?? '+'}
    </Link>
  );
}
