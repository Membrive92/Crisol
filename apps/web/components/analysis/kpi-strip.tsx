'use client';

import type { ReactNode } from 'react';

import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

import { TrendingDownIcon, TrendingUpIcon } from '@/components/ui/icons';

export type KpiStatus = 'success' | 'warning' | 'danger' | 'neutral';

export interface KpiTileProps {
  label: string;
  value: string;
  /** Δ numérico ya calculado; su signo decide la flecha y (por defecto) el color. */
  delta?: number | null;
  /** Texto del Δ ya formateado (p. ej. "-3.483 €" o "-2,1 pp"). Si falta, no se pinta Δ. */
  deltaText?: string | undefined;
  /** Línea inferior pequeña ("vs periodo anterior", "BdE < 35%", …). */
  subtitle?: string;
  /** Sparkline opcional (solo Patrimonio). Mantiene altura si falta (alineación). */
  sparkline?: ReactNode;
  /** Punto de estado (tasa de esfuerzo, etc.). */
  status?: KpiStatus;
  /** Para KPIs donde BAJAR es bueno (esfuerzo, gasto): invierte el color del Δ. */
  invertDeltaColor?: boolean;
  /**
   * PHASE-37.3 — pill sutil junto al label (p. ej. "Estruct. +9 pp" cuando
   * la tasa estructural difiere de la bruta). Se omite si no aporta.
   */
  badge?: string | undefined;
  /** Tooltip nativo (title) con la explicación ampliada del tile. */
  title?: string | undefined;
}

const STATUS_COLOR: Record<KpiStatus, string> = {
  success: colors.success,
  warning: colors.warning,
  danger: colors.danger,
  neutral: colors.textSubtle,
};

/** Un tile del strip. Componente "tonto" y testable. */
export function KpiTile({
  label,
  value,
  delta,
  deltaText,
  subtitle,
  sparkline,
  status,
  invertDeltaColor = false,
  badge,
  title,
}: KpiTileProps) {
  const hasDelta = delta != null && deltaText != null;
  const positive = (delta ?? 0) >= 0;
  // Color: por defecto subir = success; con invertDeltaColor, subir = danger.
  const good = invertDeltaColor ? !positive : positive;
  const deltaColor = good ? colors.success : colors.danger;

  return (
    <div
      title={title}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
        padding: `${spacing.sm}px ${spacing.md}px`,
        minWidth: 0,
      }}
    >
      <span
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          fontSize: 10,
          fontWeight: fontWeight.semibold,
          letterSpacing: '0.05em',
          textTransform: 'uppercase',
          color: colors.textMuted,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {label}
        {badge ? (
          <span
            style={{
              flex: '0 0 auto',
              padding: '1px 6px',
              borderRadius: 999,
              backgroundColor: colors.primarySoft,
              color: colors.primary,
              fontSize: 9,
              fontWeight: fontWeight.bold,
              letterSpacing: '0.02em',
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {badge}
          </span>
        ) : null}
      </span>
      <span
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          fontSize: fontSize.xl,
          fontWeight: fontWeight.bold,
          color: colors.text,
          letterSpacing: '-0.01em',
          fontVariantNumeric: 'tabular-nums',
          lineHeight: 1.1,
        }}
      >
        {value}
        {status ? (
          <span
            aria-hidden
            style={{
              width: 8,
              height: 8,
              borderRadius: 999,
              backgroundColor: STATUS_COLOR[status],
              flexShrink: 0,
            }}
          />
        ) : null}
      </span>
      {hasDelta ? (
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 3,
            fontSize: fontSize.xs,
            fontWeight: fontWeight.semibold,
            color: deltaColor,
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {positive ? <TrendingUpIcon size={13} /> : <TrendingDownIcon size={13} />}
          {deltaText}
        </span>
      ) : (
        // Placeholder invisible: mantiene la misma altura que un tile con Δ.
        <span style={{ fontSize: fontSize.xs, visibility: 'hidden' }}>—</span>
      )}
      {sparkline ? (
        <div style={{ marginTop: 2 }}>{sparkline}</div>
      ) : subtitle ? (
        <span style={{ fontSize: 10, color: colors.textSubtle }}>{subtitle}</span>
      ) : (
        <span style={{ fontSize: 10, visibility: 'hidden' }}>—</span>
      )}
    </div>
  );
}

/** Contenedor: 5 tiles en fila, con divisores; scrollable en móvil. */
export function KpiStrip({ children }: { children: ReactNode }) {
  return (
    <div
      role="group"
      aria-label="Indicadores clave"
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(5, minmax(0, 1fr))',
        backgroundColor: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.md,
        overflow: 'hidden',
      }}
    >
      {children}
    </div>
  );
}

/**
 * Mini-sparkline para el tile de Patrimonio: `values` mensuales. Path a mano
 * (sin libs), con un círculo en el último punto. `up` colorea la línea.
 */
export function MiniSparkline({ values, up }: { values: number[]; up: boolean }) {
  const width = 150;
  const height = 26;
  const padY = 3;
  if (values.length < 2) {
    return <div style={{ height }} aria-hidden />;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const stepX = width / (values.length - 1);
  const toY = (v: number) => padY + (1 - (v - min) / range) * (height - padY * 2);
  const points = values.map((v, i) => ({ x: i * stepX, y: toY(v) }));
  const path = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
    .join(' ');
  const last = points[points.length - 1] ?? { x: 0, y: padY };
  const stroke = up ? colors.success : colors.danger;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      height={height}
      preserveAspectRatio="none"
      aria-hidden
      style={{ display: 'block' }}
    >
      <path d={path} stroke={stroke} strokeWidth={1.5} fill="none" />
      <circle cx={last.x} cy={last.y} r={2.5} fill={stroke} />
    </svg>
  );
}
