'use client';

import type { ReactNode } from 'react';

import { colors, fontSize, fontWeight, spacing } from '@crisol/ui';

import { IconAlert } from '@/components/auth/icons';

export interface AuthCardProps {
  title: string;
  subtitle?: string | undefined;
  errorMessage?: string | undefined;
  footer?: ReactNode;
  children: ReactNode;
}

/**
 * Wrapper visual de los formularios de auth: título + subtítulo, alerta
 * de error en card (no parrafito centrado), área del formulario y un
 * footer opcional para el cambio entre login/register. Reutilizable
 * entre `/login`, `/register` y futuras pantallas (forgot, etc).
 */
export function AuthCard({
  title,
  subtitle,
  errorMessage,
  footer,
  children,
}: AuthCardProps) {
  return (
    <div>
      <header style={{ marginBottom: spacing.lg }}>
        <h1
          style={{
            margin: 0,
            fontSize: fontSize.xxl,
            fontWeight: fontWeight.bold,
            color: colors.text,
            letterSpacing: '-0.01em',
          }}
        >
          {title}
        </h1>
        {subtitle ? (
          <p
            style={{
              margin: `${spacing.xs}px 0 0 0`,
              fontSize: fontSize.sm,
              color: colors.textMuted,
              lineHeight: 1.5,
            }}
          >
            {subtitle}
          </p>
        ) : null}
      </header>

      {errorMessage ? (
        <div
          role="alert"
          style={{
            display: 'flex',
            gap: spacing.sm,
            alignItems: 'flex-start',
            padding: `${spacing.sm + 2}px ${spacing.md}px`,
            marginBottom: spacing.md,
            border: `1px solid ${colors.danger}`,
            borderRadius: 6,
            // Tinte rojo translúcido, mejor que rgba hardcoded para que
            // el dark mode también lo vea suave (la opacidad sobre el bg
            // oscuro deja un rojo apagado, sobre el bg claro un rosita).
            background: 'color-mix(in srgb, var(--color-danger) 12%, transparent)',
            color: colors.danger,
            fontSize: fontSize.sm,
            lineHeight: 1.4,
          }}
        >
          <span style={{ flexShrink: 0, marginTop: 1 }}>
            <IconAlert size={18} />
          </span>
          <span style={{ flex: 1 }}>{errorMessage}</span>
        </div>
      ) : null}

      {children}

      {footer ? (
        <div
          style={{
            marginTop: spacing.lg,
            paddingTop: spacing.md,
            borderTop: `1px solid ${colors.border}`,
            textAlign: 'center',
            fontSize: fontSize.sm,
            color: colors.textMuted,
          }}
        >
          {footer}
        </div>
      ) : null}
    </div>
  );
}
