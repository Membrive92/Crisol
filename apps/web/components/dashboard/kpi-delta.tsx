'use client';

import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';

export interface KpiDeltaProps {
  /** Valor actual ya parseado a número. */
  current: number;
  /** Valor del periodo previo (puede ser null si el backend no lo devuelve). */
  previous: number | null;
  /**
   * Polaridad: si `up=good`, un valor mayor es positivo (verde). Para
   * gastos invertimos (`up=bad`): subir gastos es negativo.
   */
  polarity?: 'up=good' | 'up=bad' | undefined;
}

/**
 * Indicador "vs periodo anterior". Pinta flecha + porcentaje + caption.
 * No renderiza nada si no hay `previous` o si el delta es exactamente
 * 0 — evitamos ruido en los KPIs.
 */
export function KpiDelta({ current, previous, polarity = 'up=good' }: KpiDeltaProps) {
  if (previous === null) return null;

  const diff = current - previous;
  if (diff === 0) {
    return (
      <span
        style={{
          fontSize: fontSize.xs,
          fontWeight: fontWeight.medium,
          color: colors.textMuted,
        }}
      >
        Sin cambio · vs periodo anterior
      </span>
    );
  }

  // Si el periodo previo es 0 no podemos sacar % — mostramos sólo signo.
  const percent =
    previous === 0 ? null : ((diff / Math.abs(previous)) * 100).toFixed(1);
  const isUp = diff > 0;
  const isPositive = polarity === 'up=good' ? isUp : !isUp;
  const arrow = isUp ? '↑' : '↓';
  const color = isPositive ? colors.success : colors.danger;
  const sign = isUp ? '+' : '';

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: spacing.xs,
        fontSize: fontSize.xs,
        fontWeight: fontWeight.medium,
      }}
    >
      <span style={{ color, fontWeight: fontWeight.semibold }}>
        {arrow}
        {percent !== null ? ` ${sign}${percent}%` : ` ${sign}—`}
      </span>
      <span style={{ color: colors.textSubtle }}>vs periodo anterior</span>
    </span>
  );
}
