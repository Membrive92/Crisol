'use client';

import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react';

import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

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

export interface FieldProps {
  label: string;
  error?: string | undefined;
  children: ReactNode;
}

export function Field({ label, error, children }: FieldProps) {
  return (
    <label style={{ display: 'block', marginBottom: spacing.md }}>
      <span style={labelStyle}>{label}</span>
      {children}
      {error ? <div style={errorStyle}>{error}</div> : null}
    </label>
  );
}

export interface TextInputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string | undefined;
}

export function TextInput({ label, error, style, ...rest }: TextInputProps) {
  return (
    <Field label={label} error={error}>
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
  children: ReactNode;
}

export function Select({ label, error, children, style, ...rest }: SelectProps) {
  return (
    <Field label={label} error={error}>
      <select {...rest} style={{ ...controlStyle, ...style }}>
        {children}
      </select>
    </Field>
  );
}
