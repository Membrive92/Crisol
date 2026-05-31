'use client';

import type { CSSProperties } from 'react';

import { colors, radius, spacing } from '@crisol/ui';

export interface SkeletonProps {
  /** Ancho del bloque (px o cualquier unidad CSS). Default '100%'. */
  width?: number | string;
  /** Alto del bloque en px. Default 16. */
  height?: number | string;
  /** Radio de las esquinas. Default `radius.sm`. */
  borderRadius?: number;
  /** Override de estilos. */
  style?: CSSProperties;
}

/**
 * Bloque de carga "shimmer". Reemplaza los `<p>Cargando…</p>` sueltos
 * por placeholders con la forma del contenido real, reduciendo el
 * layout shift al resolver la query (AUDIT-2026-05).
 *
 * El keyframe se inyecta una sola vez vía `<style>` (mismo patrón que
 * `Spinner`). `aria-hidden` porque es decorativo — el estado de carga
 * accesible lo comunica el contenedor con `aria-busy`.
 */
export function Skeleton({
  width = '100%',
  height = 16,
  borderRadius = radius.sm,
  style,
}: SkeletonProps) {
  return (
    <span
      aria-hidden
      style={{
        display: 'block',
        width,
        height,
        borderRadius,
        background: `linear-gradient(90deg, ${colors.surfaceMuted} 25%, ${colors.border} 37%, ${colors.surfaceMuted} 63%)`,
        backgroundSize: '400% 100%',
        animation: 'crisol-skeleton 1.4s ease infinite',
        ...style,
      }}
    >
      <style>{`@keyframes crisol-skeleton { 0% { background-position: 100% 50%; } 100% { background-position: 0 50%; } }`}</style>
    </span>
  );
}

export interface SkeletonCardListProps {
  /** Número de filas-placeholder. Default 3. */
  rows?: number;
}

/**
 * Lista de tarjetas-placeholder, equivalente visual a una lista de
 * `Card` mientras carga. Útil en las ramas `isLoading` de las páginas
 * que listan pares/presupuestos/gastos.
 */
export function SkeletonCardList({ rows = 3 }: SkeletonCardListProps) {
  return (
    <div
      aria-busy
      aria-live="polite"
      style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}
    >
      {Array.from({ length: rows }, (_, i) => (
        <div
          key={i}
          style={{
            backgroundColor: colors.surface,
            border: `1px solid ${colors.border}`,
            borderRadius: radius.md,
            padding: spacing.md,
            display: 'flex',
            flexDirection: 'column',
            gap: spacing.sm,
          }}
        >
          <Skeleton width="40%" height={18} />
          <Skeleton width="70%" height={14} />
        </div>
      ))}
    </div>
  );
}
