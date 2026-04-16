'use client';

import type { ButtonHTMLAttributes, CSSProperties } from 'react';

import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  fullWidth?: boolean;
}

const variantStyles: Record<ButtonVariant, CSSProperties> = {
  primary: { backgroundColor: colors.primary, color: colors.surface, border: 'none' },
  secondary: {
    backgroundColor: colors.surface,
    color: colors.primary,
    border: `1px solid ${colors.primary}`,
  },
  danger: { backgroundColor: colors.danger, color: colors.surface, border: 'none' },
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
