'use client';

import type { CSSProperties, ReactNode } from 'react';

import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';

import { Card } from '@/components/ui/card';

export interface KpiCardProps {
  /** Label corto encima del valor (`caption` muted). */
  label: string;
  /** Valor principal — string ya formateado por el caller. */
  value: string;
  /** Color del valor (default: `colors.text`). Útil para income/expense. */
  valueColor?: string | undefined;
  /**
   * Slot a la derecha de la cabecera, alineado con `label`. Para
   * iconos, badges (RECURRENTE) o action-menus (more_horiz).
   */
  trailing?: ReactNode;
  /**
   * Slot bajo el valor. Para deltas vs periodo anterior, barras de
   * presupuesto, sub-textos. Sin estilo predefinido — el caller decide.
   */
  footer?: ReactNode;
  /** Override del estilo del Card contenedor (gap, padding extra…). */
  style?: CSSProperties | undefined;
}

/**
 * Tarjeta KPI estándar. Cabecera (label + slot trailing), valor grande,
 * footer opcional. Tipografía:
 *  - label: caption (12 px medium muted)
 *  - value: display (32 px bold tabular-nums)
 *
 * Pensada para los KPIs del dashboard. Reusable en otros sitios donde
 * haga falta destacar un número (ej. resumen de import).
 */
export function KpiCard({ label, value, valueColor, trailing, footer, style }: KpiCardProps) {
  return (
    <Card
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: spacing.xs,
        padding: spacing.md,
        ...style,
      }}
    >
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: spacing.sm,
        }}
      >
        <span
          style={{
            fontSize: fontSize.xs,
            fontWeight: fontWeight.medium,
            color: colors.textMuted,
          }}
        >
          {label}
        </span>
        {trailing ? <span style={{ flex: '0 0 auto' }}>{trailing}</span> : null}
      </header>
      <span
        style={{
          fontSize: fontSize.xxl,
          fontWeight: fontWeight.bold,
          color: valueColor ?? colors.text,
          letterSpacing: '-0.01em',
          fontVariantNumeric: 'tabular-nums',
          lineHeight: 1.15,
        }}
      >
        {value}
      </span>
      {footer ? <div style={{ marginTop: spacing.xs }}>{footer}</div> : null}
    </Card>
  );
}
