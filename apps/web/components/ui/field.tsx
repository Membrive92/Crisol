'use client';

import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react';

import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

const labelStyle = {
  display: 'block',
  marginBottom: spacing.xs,
  fontSize: fontSize.sm,
  fontWeight: fontWeight.medium,
  color: colors.text,
} as const;

const controlStyle = {
  width: '100%',
  padding: `${spacing.sm}px ${spacing.sm}px`,
  borderRadius: radius.sm,
  border: `1px solid ${colors.border}`,
  fontSize: fontSize.md,
  backgroundColor: colors.surface,
  color: colors.text,
  boxSizing: 'border-box' as const,
};

const errorStyle = {
  marginTop: spacing.xs,
  fontSize: fontSize.xs,
  color: colors.danger,
} as const;

const hintStyle = {
  marginTop: spacing.xs,
  fontSize: fontSize.xs,
  color: colors.textMuted,
} as const;

interface FieldProps {
  label: string;
  error?: string | undefined;
  /** Texto de ayuda que se muestra bajo el control. */
  hint?: string | undefined;
  /**
   * Sin margen inferior. Para campos colocados en una fila inline junto a
   * un botón (`alignItems: flex-end`): el margen del campo desalinearía el
   * botón, que quedaría por debajo del control.
   */
  dense?: boolean | undefined;
  children: ReactNode;
}

function Field({ label, error, hint, dense, children }: FieldProps) {
  return (
    <label style={{ display: 'block', marginBottom: dense ? 0 : spacing.md }}>
      <span style={labelStyle}>{label}</span>
      {children}
      {hint ? <div style={hintStyle}>{hint}</div> : null}
      {error ? <div style={errorStyle}>{error}</div> : null}
    </label>
  );
}

export interface TextInputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string | undefined;
  hint?: string | undefined;
  dense?: boolean | undefined;
}

export function TextInput({ label, error, hint, dense, style, ...rest }: TextInputProps) {
  return (
    <Field label={label} error={error} hint={hint} dense={dense}>
      <input {...rest} style={{ ...controlStyle, ...style }} />
    </Field>
  );
}

export interface TextAreaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  error?: string | undefined;
}

export function TextArea({ label, error, style, ...rest }: TextAreaProps) {
  return (
    <Field label={label} error={error}>
      <textarea {...rest} style={{ ...controlStyle, minHeight: 80, ...style }} />
    </Field>
  );
}

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  error?: string | undefined;
  dense?: boolean | undefined;
  children: ReactNode;
}

export function Select({ label, error, dense, children, style, ...rest }: SelectProps) {
  return (
    <Field label={label} error={error} dense={dense}>
      <select {...rest} style={{ ...controlStyle, ...style }}>
        {children}
      </select>
    </Field>
  );
}
