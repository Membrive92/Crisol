'use client';

import type { ButtonHTMLAttributes } from 'react';

import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

export interface SubmitButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  loading?: boolean;
  loadingLabel?: string;
}

/**
 * Botón de submit del flow de auth con spinner integrado. El loadingLabel
 * mantiene la accesibilidad (lector de pantalla) y se oculta visualmente
 * cuando hay spinner.
 */
export function SubmitButton({
  loading,
  loadingLabel = 'Procesando…',
  children,
  disabled,
  ...rest
}: SubmitButtonProps) {
  const isDisabled = disabled || loading;
  return (
    <button
      type="submit"
      aria-busy={loading || undefined}
      disabled={isDisabled}
      {...rest}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: spacing.sm,
        width: '100%',
        padding: `${spacing.sm + 4}px ${spacing.md}px`,
        backgroundColor: colors.primary,
        color: colors.onPrimary,
        border: 'none',
        borderRadius: radius.sm,
        fontSize: fontSize.md,
        fontWeight: fontWeight.semibold,
        cursor: isDisabled ? 'not-allowed' : 'pointer',
        opacity: isDisabled ? 0.7 : 1,
        transition: 'opacity 120ms ease, transform 120ms ease',
        ...rest.style,
      }}
    >
      {loading ? (
        <>
          <Spinner />
          <span>{loadingLabel}</span>
        </>
      ) : (
        children
      )}
    </button>
  );
}

function Spinner() {
  return (
    <span
      aria-hidden="true"
      style={{
        display: 'inline-block',
        width: 16,
        height: 16,
        border: '2px solid rgba(255, 255, 255, 0.4)',
        borderTopColor: colors.onPrimary,
        borderRadius: '50%',
        animation: 'auth-spinner 0.7s linear infinite',
      }}
    />
  );
}
