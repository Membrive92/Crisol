'use client';

import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';

import { Card } from '@/components/ui/card';

/**
 * Tarjeta de "Consejo financiero". Por ahora copy estático. Follow-up:
 * cablear al módulo `ai` para generar consejos en función de los datos
 * reales del usuario (PHASE-7.1.1).
 */
export function TipCard() {
  return (
    <Card
      style={{
        backgroundColor: colors.primarySoft,
        border: `1px solid ${colors.border}`,
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
          color: colors.primary,
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
        }}
      >
        Consejo financiero
      </span>
      <p
        style={{
          margin: 0,
          fontSize: fontSize.sm,
          color: colors.text,
          lineHeight: 1.5,
        }}
      >
        Aprovecha los tickets para registrar tus gastos sin escribir importes a
        mano. La IA local extrae merchant, fecha y total — tú confirmas o
        corriges en segundos.
      </p>
      <span
        style={{
          marginTop: spacing.xs,
          fontSize: fontSize.xs,
          color: colors.textSubtle,
        }}
      >
        Próximamente: consejos personalizados a partir de tus datos.
      </span>
    </Card>
  );
}
