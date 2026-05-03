'use client';

import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';

import { Card } from '@/components/ui/card';

export interface ComingSoonCardProps {
  title: string;
  description: string;
}

/**
 * Card "próximamente" para feature aún no implementada. Estilo
 * deliberadamente discreto: bg `surface-muted`, sin bordes fuertes,
 * para que no compita visualmente con secciones que sí tienen datos.
 */
export function ComingSoonCard({ title, description }: ComingSoonCardProps) {
  return (
    <Card
      style={{
        backgroundColor: colors.surfaceMuted,
        border: `1px dashed ${colors.border}`,
        padding: spacing.md,
        display: 'flex',
        flexDirection: 'column',
        gap: spacing.xs,
      }}
    >
      <span
        style={{
          fontSize: fontSize.xs,
          fontWeight: fontWeight.semibold,
          color: colors.textSubtle,
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
        }}
      >
        Próximamente
      </span>
      <span
        style={{
          fontSize: fontSize.md,
          fontWeight: fontWeight.semibold,
          color: colors.text,
        }}
      >
        {title}
      </span>
      <p
        style={{
          margin: 0,
          fontSize: fontSize.sm,
          color: colors.textMuted,
          lineHeight: 1.5,
        }}
      >
        {description}
      </p>
    </Card>
  );
}
