'use client';

import type { ButtonHTMLAttributes, CSSProperties } from 'react';

import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  fullWidth?: boolean;
}

// Convenciones de variantes:
// - `primary`   → CTA fuerte (sólido). Usar para la acción dominante de la
//                  pantalla: "Confirmar", "Iniciar sesión", "Analizar ticket".
// - `secondary` → CTA secundario (outlined). Usar para acciones de soporte
//                  como "+ Subir ticket" desde un listado o "Cancelar".
// - `danger`    → destructivo. Sólido rojo.
// - `ghost`     → neutro con borde sutil. Paginación, cancelar inline.
const variantStyles: Record<ButtonVariant, CSSProperties> = {
  primary: {
    backgroundColor: colors.primary,
    color: colors.onPrimary,
    border: `1px solid ${colors.primary}`,
  },
  secondary: {
    backgroundColor: 'transparent',
    color: colors.primary,
    border: `1px solid ${colors.primary}`,
  },
  danger: {
    backgroundColor: colors.danger,
    color: colors.onPrimary,
    border: `1px solid ${colors.danger}`,
  },
  ghost: {
    backgroundColor: 'transparent',
    color: colors.text,
    border: `1px solid ${colors.border}`,
  },
};

export function Button({
  variant = 'primary',
  fullWidth = false,
  disabled,
  style,
  ...rest
}: ButtonProps) {
  const base: CSSProperties = {
    padding: `${spacing.sm}px ${spacing.md}px`,
    borderRadius: radius.md,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.5 : 1,
    width: fullWidth ? '100%' : 'auto',
    transition: 'opacity 150ms ease',
  };

  return (
    <button
      {...rest}
      disabled={disabled}
      style={{ ...base, ...variantStyles[variant], ...style }}
    />
  );
}
