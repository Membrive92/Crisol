'use client';

import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react';

import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

export interface AuthInputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  /** SVG icon que se pinta a la izquierda del input. */
  icon?: ReactNode;
  /** Mensaje de error inline. Si está, se pinta debajo en rojo. */
  errorMessage?: string | undefined;
  /** Texto auxiliar debajo del input (formato esperado, etc). */
  hint?: string | undefined;
}

export const AuthInput = forwardRef<HTMLInputElement, AuthInputProps>(
  function AuthInput({ label, icon, errorMessage, hint, id, ...rest }, ref) {
    const inputId = id ?? `field-${label.toLowerCase().replace(/\s+/g, '-')}`;

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.xs }}>
        <label
          htmlFor={inputId}
          style={{
            fontSize: fontSize.sm,
            fontWeight: fontWeight.medium,
            color: colors.text,
          }}
        >
          {label}
        </label>
        <div style={{ position: 'relative' }}>
          {icon ? (
            <span
              aria-hidden="true"
              style={{
                position: 'absolute',
                left: spacing.sm + 2,
                top: '50%',
                transform: 'translateY(-50%)',
                color: colors.textMuted,
                display: 'inline-flex',
                pointerEvents: 'none',
              }}
            >
              {icon}
            </span>
          ) : null}
          <input
            ref={ref}
            id={inputId}
            aria-invalid={errorMessage ? 'true' : undefined}
            aria-describedby={
              errorMessage
                ? `${inputId}-error`
                : hint
                  ? `${inputId}-hint`
                  : undefined
            }
            {...rest}
            style={{
              width: '100%',
              padding: `${spacing.sm + 2}px ${spacing.md}px`,
              paddingLeft: icon ? spacing.xl + 8 : spacing.md,
              border: `1px solid ${errorMessage ? colors.danger : colors.border}`,
              borderRadius: radius.sm,
              fontSize: fontSize.md,
              backgroundColor: colors.surface,
              color: colors.text,
              boxSizing: 'border-box',
              transition: 'border-color 120ms ease',
              ...rest.style,
            }}
          />
        </div>
        {errorMessage ? (
          <span
            id={`${inputId}-error`}
            style={{
              fontSize: fontSize.xs,
              color: colors.danger,
            }}
          >
            {errorMessage}
          </span>
        ) : hint ? (
          <span
            id={`${inputId}-hint`}
            style={{
              fontSize: fontSize.xs,
              color: colors.textMuted,
            }}
          >
            {hint}
          </span>
        ) : null}
      </div>
    );
  },
);
