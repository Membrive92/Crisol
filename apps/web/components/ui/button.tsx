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
// Borde en longhand (borderWidth/Style/Color), NO el shorthand `border`: hay
// callers que sobreescriben sólo `borderColor` vía `style` (p.ej. budget-row),
// y mezclar shorthand+longhand hace que React avise al re-render cuando el
// longhand aparece/desaparece. El render es idéntico a `1px solid X`.
const variantStyles: Record<ButtonVariant, CSSProperties> = {
  primary: {
    backgroundColor: colors.primary,
    color: colors.onPrimary,
    borderWidth: 1,
    borderStyle: 'solid',
    borderColor: colors.primary,
  },
  secondary: {
    backgroundColor: 'transparent',
    color: colors.primary,
    borderWidth: 1,
    borderStyle: 'solid',
    borderColor: colors.primary,
  },
  danger: {
    backgroundColor: colors.danger,
    color: colors.onPrimary,
    borderWidth: 1,
    borderStyle: 'solid',
    borderColor: colors.danger,
  },
  ghost: {
    backgroundColor: 'transparent',
    color: colors.text,
    borderWidth: 1,
    borderStyle: 'solid',
    borderColor: colors.border,
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
