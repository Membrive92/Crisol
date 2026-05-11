'use client';

import type { CSSProperties } from 'react';

import { colors } from '@crisol/ui';

export interface SpinnerProps {
  /** Tamaño del SVG en px. Default 16. */
  size?: number;
  /** Color del trazo. Default `colors.primary`. */
  color?: string;
  /** Override de estilos del wrapper. */
  style?: CSSProperties;
  /** Label accesible. Default "Cargando". */
  label?: string;
}

/**
 * Spinner SVG con animación CSS. Usado para feedback visual de
 * operaciones en curso (IA local, exports largos, etc.).
 *
 * Inline-block: se puede colocar al lado de texto en botones, en el
 * header de una sección, o dentro de un toast tipo `loading`.
 */
export function Spinner({
  size = 16,
  color,
  style,
  label = 'Cargando',
}: SpinnerProps) {
  const stroke = color ?? colors.primary;
  const radius = size / 2 - 2;
  const c = size / 2;
  return (
    <span
      role="status"
      aria-label={label}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: size,
        height: size,
        ...style,
      }}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        style={{ animation: 'finanzas-spin 1s linear infinite' }}
      >
        <circle
          cx={c}
          cy={c}
          r={radius}
          stroke={stroke}
          strokeOpacity={0.2}
          strokeWidth={2}
          fill="none"
        />
        <circle
          cx={c}
          cy={c}
          r={radius}
          stroke={stroke}
          strokeWidth={2}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={Math.PI * 2 * radius}
          strokeDashoffset={Math.PI * 2 * radius * 0.75}
        />
      </svg>
      {/* Inyecta el keyframes una vez. styled-jsx no es global, pero
          un <style> raw sí. Si esto se usa mucho, mover a globals.css. */}
      <style>{`@keyframes finanzas-spin { to { transform: rotate(360deg); } }`}</style>
    </span>
  );
}
